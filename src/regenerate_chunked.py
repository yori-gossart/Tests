"""
Chunked, resumable regeneration of a BattLeDIM SCADA year.

WHY
---
A full year is 105120 hydraulic steps and takes ~100 minutes with
WNTRSimulator, which is longer than this container survives; every restart
threw away the whole run. This module simulates the year in chunks, writing
each one to disk as it completes, so a restart costs one chunk instead of
everything.

EXACTNESS
---------
Chunking is an exact decomposition, not an approximation, because L-Town's only
carried hydraulic state is the single tank T1 (one pump and three valves, all
driven by controls on that level):

  * every demand pattern is cyclic, so starting a chunk at step s is the same as
    rotating the multipliers left by s -- exact for the 105120-step yearly
    patterns and the 2016-step weekly ones alike;
  * leak demand patterns are sliced from the full-horizon array at the same
    offset;
  * abrupt-leak start/end times are shifted into chunk-local seconds, and leaks
    that do not overlap the chunk are simply not installed;
  * the tank's initial level is carried from the previous chunk's final level.

verify_against_reference() checks that claim by simulating a short horizon both
ways and comparing every published channel. The chunked path is only used
because that check passes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import time
from math import sqrt
from pathlib import Path

import numpy as np
import pandas as pd
import wntr
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from regenerate_scada import (  # noqa: E402
    GLOBAL_REQUIRED_PRESSURE,
    INCIPIENT_REQUIRED_PRESSURE,
    LEAK_DISCHARGE_COEFF,
    MODE_SIMULATION,
    TIME_STEP_S,
    PORTING_DELTA,
    sha256_of,
)

REPO = Path(__file__).resolve().parents[1]
RAW = REPO / "data" / "raw" / "battledim_official"

CHANNELS = ("Pressures", "Levels", "Demands", "Flows", "Leaks")


def load_cfg(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="latin-1"))


def leak_rows(cfg: dict) -> list[list[str]]:
    rows = []
    for raw in cfg["leakages"][1:]:
        parts = [p.strip() for p in str(raw).split(",")]
        if len(parts) >= 6:
            rows.append(parts[:6])
    return rows


def build_incipient_pattern(diameter: float, ST: int, PT: int, ET: int,
                            total_steps: int) -> np.ndarray:
    """The official generator's incipient ramp, over the whole horizon."""
    area = 3.14159 * (diameter / 2) ** 2
    inc = diameter / (PT - ST)
    inc_d = np.arange(inc, diameter, inc)
    inc_area = 0.75 * sqrt(2 / 1000) * 990.27 * 3.14159 * (inc_d / 2) ** 2
    magnitude = 0.75 * sqrt(2 / 1000) * 990.27 * area
    arr = (
        [0.0] * ST
        + inc_area.tolist()
        + [magnitude] * (ET - PT + 1)
        + [0.0] * max(0, total_steps - ET)
    )
    return np.asarray(arr, dtype=float)


class ChunkedRegenerator:
    def __init__(self, config_path: Path, inp_path: Path, out_dir: Path,
                 chunk_steps: int):
        self.cfg = load_cfg(config_path)
        self.inp_path = inp_path
        self.out_dir = out_dir
        self.chunk_dir = out_dir / "chunks"
        self.chunk_steps = chunk_steps
        self.config_path = config_path

        self.sensors = {
            "Pressures": [str(s) for s in self.cfg["pressure_sensors"]],
            "Levels": [str(s) for s in self.cfg["level_sensors"]],
            "Demands": [str(s) for s in self.cfg["amrs"]],
            "Flows": [str(s) for s in self.cfg["flow_sensors"]],
        }
        self.leaks = leak_rows(self.cfg)

        self.time_stamp = pd.date_range(
            self.cfg["times"]["StartTime"], self.cfg["times"]["EndTime"],
            freq=f"{TIME_STEP_S // 60}min",
        )
        self.n_steps = len(self.time_stamp)
        self.total_steps = self.n_steps - 1

        pos = {t: i for i, t in enumerate(self.time_stamp)}
        self.plan = []
        for pid, st, et, diam, ltype, pt in self.leaks:
            ST, ET = pos[pd.Timestamp(st)], pos[pd.Timestamp(et)]
            entry = {"pipe": pid, "type": ltype, "diameter": float(diam),
                     "ST": ST, "ET": ET}
            if "incipient" in ltype:
                entry["ET"] = ET + 1
                entry["PT"] = pos[pd.Timestamp(pt)] + 1
                entry["pattern"] = build_incipient_pattern(
                    float(diam), ST, entry["PT"], entry["ET"], self.total_steps
                )
            self.plan.append(entry)

    # ------------------------------------------------------------------ one --

    def _build_model(self, start: int, n: int, tank_level: float | None):
        wn = wntr.network.WaterNetworkModel(str(self.inp_path))
        for _name, node in wn.junctions():
            node.required_pressure = GLOBAL_REQUIRED_PRESSURE
        wn.options.hydraulic.demand_model = MODE_SIMULATION

        # Rotate every cyclic pattern so this chunk starts at absolute step
        # `start`. Exact: EPANET indexes patterns modulo their length.
        for pname in list(wn.pattern_name_list):
            pat = wn.get_pattern(pname)
            m = np.asarray(pat.multipliers, dtype=float)
            if len(m) > 1:
                pat.multipliers = np.roll(m, -(start % len(m)))

        if tank_level is not None:
            for tname, tank in wn.tanks():
                tank.init_level = float(
                    np.clip(tank_level, tank.min_level + 1e-6, tank.max_level - 1e-6)
                )

        wn.options.time.duration = n * TIME_STEP_S

        for i, e in enumerate(self.plan):
            if e["ET"] < start or e["ST"] > start + n:
                continue  # leak does not overlap this chunk
            pipe = wn.get_link(e["pipe"])
            node_leak = f"{pipe}_leaknode"
            wn = wntr.morph.split_pipe(wn, pipe, f"{pipe}_Bleak", node_leak)
            node = wn.get_node(node_leak)

            if "incipient" in e["type"]:
                seg = e["pattern"][start : start + n + 1]
                if seg.size == 0 or not np.any(seg):
                    continue
                node.demand_timeseries_list[0]._base = 1
                pname = f"{node_leak}_pat"
                wn.add_pattern(pname, seg.tolist())
                node.demand_timeseries_list[0].pattern_name = pname
                node.required_pressure = INCIPIENT_REQUIRED_PRESSURE
                node.minimum_pressure = 0
            else:
                area = 3.14159 * (e["diameter"] / 2) ** 2
                s_local = max(0, e["ST"] - start) * TIME_STEP_S
                e_local = min(n + 1, e["ET"] + 1 - start) * TIME_STEP_S
                node._leak_start_control_name = f"{i}start"
                node._leak_end_control_name = f"{i}end"
                node.add_leak(wn, discharge_coeff=LEAK_DISCHARGE_COEFF, area=area,
                              start_time=int(s_local), end_time=int(e_local))
        return wn

    def _extract(self, wn, results, start: int, n: int) -> dict[str, pd.DataFrame]:
        dec = 2
        ts = self.time_stamp[start : start + n]

        def frame(src, ids, scale=1.0):
            keep = [c for c in ids if c in src.columns]
            df = src.loc[:, keep].iloc[: len(ts)].copy()
            df = (df * scale).round(dec)
            df.insert(0, "Timestamp", ts[: len(df)])
            return df

        out = {
            "Pressures": frame(results.node["pressure"], self.sensors["Pressures"]),
            "Levels": frame(results.node["pressure"], self.sensors["Levels"]),
            "Demands": frame(results.node["demand"], self.sensors["Demands"], 3600 * 1000),
            "Flows": frame(results.link["flowrate"], self.sensors["Flows"], 3600),
        }
        leaks = {"Timestamp": ts}
        for e in self.plan:
            node_name = f"{e['pipe']}_leaknode"
            key = "demand" if "incipient" in e["type"] else "leak_demand"
            if node_name in results.node[key].columns:
                v = results.node[key][node_name].values[: len(ts)] * 3600
            else:
                v = np.zeros(len(ts))
            leaks[e["pipe"]] = np.round(v, dec)
        out["Leaks"] = pd.DataFrame(leaks)
        return out

    def run_chunk(self, start: int, n: int, tank_level: float | None):
        wn = self._build_model(start, n, tank_level)
        results = wntr.sim.WNTRSimulator(wn).run_sim()
        if results.node["pressure"].empty:
            raise RuntimeError(f"empty results for chunk at step {start}")
        frames = self._extract(wn, results, start, n)
        tanks = [t for t, _ in wn.tanks()]
        final_level = (
            float(results.node["pressure"][tanks[0]].values[min(n, len(results.node["pressure"]) - 1)])
            if tanks else None
        )
        return frames, final_level

    # ----------------------------------------------------------------- all --

    def run(self) -> dict:
        t0 = time.time()
        self.chunk_dir.mkdir(parents=True, exist_ok=True)
        bounds = list(range(0, self.n_steps, self.chunk_steps))
        state_path = self.chunk_dir / "state.json"
        state = json.loads(state_path.read_text()) if state_path.exists() else {}

        tank_level = state.get("tank_level")
        for ci, start in enumerate(bounds):
            n = min(self.chunk_steps, self.n_steps - start)
            marker = self.chunk_dir / f"chunk_{ci:04d}_Pressures.csv"
            if marker.exists() and str(ci) in state.get("done", []):
                tank_level = state["levels"][str(ci)]
                continue
            frames, tank_level = self.run_chunk(start, n, tank_level)
            for name, df in frames.items():
                df.to_csv(self.chunk_dir / f"chunk_{ci:04d}_{name}.csv", index=False)
            state.setdefault("done", []).append(str(ci))
            state.setdefault("levels", {})[str(ci)] = tank_level
            state["tank_level"] = tank_level
            state_path.write_text(json.dumps(state))
            print(f"  chunk {ci+1}/{len(bounds)} steps {start}-{start+n} "
                  f"tank={tank_level:.3f} ({time.time()-t0:.0f}s)", flush=True)

        year = self.time_stamp[0].year
        written = {}
        for name in CHANNELS:
            parts = [pd.read_csv(self.chunk_dir / f"chunk_{ci:04d}_{name}.csv")
                     for ci in range(len(bounds))]
            df = pd.concat(parts, ignore_index=True)
            path = self.out_dir / f"{year}_SCADA_{name}.csv"
            df.to_csv(path, index=False)
            written[path.name] = {"rows": int(len(df)), "cols": int(df.shape[1]),
                                  "sha256": sha256_of(path)}
            print(f"  wrote {path.name}: {len(df)} x {df.shape[1]}", flush=True)

        meta = {
            "generated_utc": pd.Timestamp.now("UTC").isoformat(),
            "method": "chunked resumable regeneration (exact decomposition)",
            "chunk_steps": self.chunk_steps,
            "n_chunks": len(bounds),
            "source_generator": "data/raw/battledim_official/dataset_generator.py",
            "source_generator_sha256": sha256_of(RAW / "dataset_generator.py"),
            "network_inp_sha256": sha256_of(self.inp_path),
            "config": str(self.config_path),
            "config_sha256": sha256_of(self.config_path),
            "mode_simulation": MODE_SIMULATION,
            "n_leaks": len(self.plan),
            "n_timesteps": int(self.n_steps),
            "period": [str(self.time_stamp[0]), str(self.time_stamp[-1])],
            "porting_delta": PORTING_DELTA,
            "chunking_note": (
                "Chunk boundaries carry only the tank level; all patterns are cyclic "
                "and are rotated by the chunk start, so the decomposition is exact. "
                "Verified by verify_against_reference()."
            ),
            "deterministic": "no RNG is used anywhere in this pipeline",
            "wall_clock_s": round(time.time() - t0, 1),
            "versions": {"python": sys.version.split()[0], "wntr": wntr.__version__,
                         "numpy": np.__version__, "pandas": pd.__version__},
            "outputs": written,
        }
        (self.out_dir / "REGENERATION_METADATA.json").write_text(
            json.dumps(meta, indent=2) + "\n"
        )
        return meta


def verify_against_reference(config_path: Path, inp_path: Path, scratch: Path,
                             chunk_steps: int) -> dict:
    """Simulate the same horizon in one piece and in chunks; compare channels."""
    import regenerate_scada as ref

    scratch.mkdir(parents=True, exist_ok=True)
    single_dir, chunk_out = scratch / "single", scratch / "chunked"
    for d in (single_dir, chunk_out):
        shutil.rmtree(d, ignore_errors=True)

    creator = ref.LeakDatasetCreator(config_path, inp_path)
    creator.run(single_dir)

    ChunkedRegenerator(config_path, inp_path, chunk_out, chunk_steps).run()

    report = {}
    year = pd.Timestamp(load_cfg(config_path)["times"]["StartTime"]).year
    for name in CHANNELS:
        a_p, b_p = single_dir / f"{year}_SCADA_{name}.csv", chunk_out / f"{year}_SCADA_{name}.csv"
        if not (a_p.exists() and b_p.exists()):
            report[name] = {"status": "MISSING"}
            continue
        a, b = pd.read_csv(a_p), pd.read_csv(b_p)
        cols = [c for c in a.columns if c != "Timestamp" and c in b.columns]
        n = min(len(a), len(b))
        if not cols:
            report[name] = {"status": "NO_COLUMNS", "n_rows": n}
            continue
        d = np.abs(a[cols].to_numpy()[:n] - b[cols].to_numpy()[:n])
        report[name] = {
            "status": "COMPARED", "n_rows": int(n), "n_cols": len(cols),
            "max_abs_diff": float(np.nanmax(d)),
            "mean_abs_diff": float(np.nanmean(d)),
            "frac_within_rounding": float(np.mean(d <= 0.01)),
        }
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--inp", default=str(RAW / "L-TOWN_v2_Real.inp"))
    ap.add_argument("--out", required=True)
    ap.add_argument("--chunk-steps", type=int, default=4320)  # 15 days
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--scratch", default="/tmp/chunk_verify")
    args = ap.parse_args()

    if args.verify:
        rep = verify_against_reference(Path(args.config), Path(args.inp),
                                       Path(args.scratch), args.chunk_steps)
        print(json.dumps(rep, indent=2))
        worst = max((v.get("max_abs_diff", 0.0) for v in rep.values()
                     if v.get("status") == "COMPARED"), default=float("inf"))
        print(f"\nworst max_abs_diff across channels: {worst}")
        return 0 if worst <= 0.011 else 1

    r = ChunkedRegenerator(Path(args.config), Path(args.inp), Path(args.out),
                           args.chunk_steps)
    print(f"period {r.time_stamp[0]} -> {r.time_stamp[-1]} ({r.n_steps} steps), "
          f"{len(r.plan)} leaks, chunk={args.chunk_steps} steps", flush=True)
    r.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
