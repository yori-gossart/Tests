"""
Regenerate the BattLeDIM SCADA series with the OFFICIAL generator semantics.

WHY THIS EXISTS
---------------
The published SCADA files (2018_SCADA_*.csv, 2019_SCADA_*.csv) live on Zenodo
record 4017659 and on battledim.ucy.ac.cy. Both hosts are denied by this
session's egress policy (exact errors in data/raw/PROVENANCE.json). What IS
recoverable is the complete generating pipeline: the official network model
(L-TOWN_v2_Real.inp), the official leak schedule (dataset_configuration.yalm)
and the official generator (dataset_generator.py). The generator is fully
deterministic -- it contains no random number draw -- so the published SCADA is
a pure function of those three artefacts.

This module is a faithful port of data/raw/battledim_official/dataset_generator.py
to Linux + wntr 1.5. Every deviation is listed in PORTING_DELTA below; none of
them touch the hydraulics.

READ data/raw/PROVENANCE.json FINDING F2 BEFORE USING THIS OUTPUT: the published
L-TOWN_v2_Real.inp carries only 365 days of demand patterns, so the 2019 half of
a two-year run repeats the 2018 demands verbatim.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from math import sqrt
from pathlib import Path

import numpy as np
import pandas as pd
import wntr
import yaml

REPO = Path(__file__).resolve().parents[1]
RAW = REPO / "data" / "raw" / "battledim_official"
OUT = REPO / "data" / "processed" / "regenerated"
LOGS = REPO / "logs"

# Verbatim from the official generator; changing any of these changes hydraulics.
MODE_SIMULATION = "PDD"
GLOBAL_REQUIRED_PRESSURE = 25.0   # generator: node.nominal_pressure = 25
INCIPIENT_REQUIRED_PRESSURE = 100.0  # generator: nominal_pres = 100
LEAK_DISCHARGE_COEFF = 0.75
TIME_STEP_S = 300

PORTING_DELTA = [
    "os.getcwd() + Windows '\\\\' path joins  ->  pathlib / os.path.join (I/O only)",
    "yaml.load(f.read())  ->  yaml.safe_load(...) (identical parse for this document)",
    "node.nominal_pressure  ->  node.required_pressure (wntr renamed the property; same variable)",
    "wntr.sim.WNTRSimulator(wn, mode='PDD')  ->  wn.options.hydraulic.demand_model='PDD' (wntr moved the switch)",
    "pd.ExcelWriter(...).save()  ->  .close() (pandas API rename)",
    "Timestamp._date_repr/._time_repr  ->  strftime('%Y-%m-%d %H:%M') (identical string)",
    "xlsx measurement workbook  ->  one CSV per quantity per year (same values, same rounding)",
]


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


class LeakDatasetCreator:
    """Port of the official LeakDatasetCreator. Hydraulic logic is unchanged."""

    def __init__(self, config_path: Path, inp_path: Path):
        with config_path.open("r", encoding="latin-1") as fh:
            cfg = yaml.safe_load(fh.read())

        self.cfg = cfg
        self.start_time = cfg["times"]["StartTime"]
        self.end_time = cfg["times"]["EndTime"]
        # Official generator drops element 0, which is the '# linkID, ...' header.
        self.leakages = cfg["leakages"][1:]
        self.number_of_leaks = len(self.leakages)

        self.pressure_sensors = [str(s) for s in cfg["pressure_sensors"]]
        self.flow_sensors = [str(s) for s in cfg["flow_sensors"]]
        self.level_sensors = [str(s) for s in cfg["level_sensors"]]
        self.amrs = [str(s) for s in cfg["amrs"]]

        self.wn = wntr.network.WaterNetworkModel(str(inp_path))

        # Official: every junction that exists BEFORE the pipe splits gets 25 m.
        # Leak nodes created later by split_pipe deliberately do not inherit it.
        for _name, node in self.wn.junctions():
            node.required_pressure = GLOBAL_REQUIRED_PRESSURE
        self.wn.options.hydraulic.demand_model = MODE_SIMULATION

        self.time_step = round(self.wn.options.time.hydraulic_timestep)
        self.time_stamp = pd.date_range(
            self.start_time, self.end_time, freq=f"{self.time_step // 60}min"
        )
        self.wn.options.time.duration = (len(self.time_stamp) - 1) * TIME_STEP_S
        self.TIMESTEPS = int(
            self.wn.options.time.duration / self.wn.options.time.hydraulic_timestep
        )

    # ---------------------------------------------------------------- leaks --

    def _install_leaks(self):
        leak_node, leak_param = {}, {}
        leak_meta = []

        for i in range(self.number_of_leaks):
            line = [p.strip() for p in str(self.leakages[i]).split(",")]
            link_id, st_s, et_s, diam_s, ltype, pt_s = line[:6]

            ST = self.time_stamp.get_loc(st_s)
            ET = self.time_stamp.get_loc(et_s)

            pipe = self.wn.get_link(link_id)
            node_leak = f"{pipe}_leaknode"
            self.wn = wntr.morph.split_pipe(self.wn, pipe, f"{pipe}_Bleak", node_leak)
            leak_node[i] = self.wn.get_node(node_leak)

            diameter = float(diam_s)
            area = 3.14159 * (diameter / 2) ** 2

            if "incipient" in ltype:
                ET = ET + 1
                PT = self.time_stamp.get_loc(pt_s) + 1
                leak_param[i] = "demand"

                inc = diameter / (PT - ST)
                inc_d = np.arange(inc, diameter, inc)
                inc_area = 0.75 * sqrt(2 / 1000) * 990.27 * 3.14159 * (inc_d / 2) ** 2
                magnitude = 0.75 * sqrt(2 / 1000) * 990.27 * area
                pattern_array = (
                    [0] * ST
                    + inc_area.tolist()
                    + [magnitude] * (ET - PT + 1)
                    + [0] * (self.TIMESTEPS - ET)
                )

                leak_node[i].demand_timeseries_list[0]._base = 1
                pname = str(leak_node[i])
                self.wn.add_pattern(pname, pattern_array)
                leak_node[i].demand_timeseries_list[0].pattern_name = pname
                leak_node[i].required_pressure = INCIPIENT_REQUIRED_PRESSURE
                leak_node[i].minimum_pressure = 0

                start_ts, end_ts, peak_ts = (
                    self.time_stamp[ST],
                    self.time_stamp[ET - 1],
                    self.time_stamp[PT - 1],
                )
            else:
                leak_param[i] = "leak_demand"
                PT = ST
                leak_node[i]._leak_end_control_name = f"{i}end"
                leak_node[i]._leak_start_control_name = f"{i}start"
                leak_node[i].add_leak(
                    self.wn,
                    discharge_coeff=LEAK_DISCHARGE_COEFF,
                    area=area,
                    start_time=ST * self.time_step,
                    end_time=(ET + 1) * self.time_step,
                )
                start_ts, end_ts, peak_ts = (
                    self.time_stamp[ST],
                    self.time_stamp[ET],
                    self.time_stamp[PT],
                )

            leak_meta.append(
                {
                    "leak_pipe": link_id,
                    "leak_node": str(leak_node[i]),
                    "leak_area_m2": area,
                    "leak_diameter_m": diameter,
                    "leak_type": ltype,
                    "leak_start": start_ts.strftime("%Y-%m-%d %H:%M"),
                    "leak_end": end_ts.strftime("%Y-%m-%d %H:%M"),
                    "peak_time": peak_ts.strftime("%Y-%m-%d %H:%M"),
                }
            )

        return leak_node, leak_param, leak_meta

    # ------------------------------------------------------------------ run --

    def run(self, out_dir: Path):
        out_dir.mkdir(parents=True, exist_ok=True)
        t0 = time.time()

        leak_node, leak_param, leak_meta = self._install_leaks()
        print(f"[{time.time()-t0:7.1f}s] installed {self.number_of_leaks} leaks", flush=True)

        sim = wntr.sim.WNTRSimulator(self.wn)
        results = sim.run_sim()
        if results.node["pressure"].empty:
            raise RuntimeError("Negative pressures / empty result set.")
        print(f"[{time.time()-t0:7.1f}s] hydraulic simulation complete", flush=True)

        n = len(self.time_stamp)
        dec = 2  # decimal_size in the official generator

        def frame(source: pd.DataFrame, ids, scale=1.0):
            keep = [c for c in ids if c in source.columns]
            df = source.loc[:, keep].iloc[:n].copy()
            df = (df * scale).round(dec)
            df.insert(0, "Timestamp", self.time_stamp[: len(df)])
            return df

        pressures = frame(results.node["pressure"], self.pressure_sensors)
        levels = frame(results.node["pressure"], self.level_sensors)
        demands = frame(results.node["demand"], self.amrs, scale=3600 * 1000)  # L/h
        flows = frame(results.link["flowrate"], self.flow_sensors, scale=3600)  # m3/h

        # True leak flow per event, in m3/h (official generator's Leak_*.xlsx sheet).
        leaks_out = {"Timestamp": self.time_stamp[:n]}
        for i, meta in enumerate(leak_meta):
            series = results.node[leak_param[i]][str(leak_node[i])].values[:n] * 3600
            leaks_out[meta["leak_pipe"]] = np.round(series, dec)
        leaks_df = pd.DataFrame(leaks_out)

        written = {}
        for year in (2018, 2019):
            mask = pressures["Timestamp"].dt.year == year
            if not mask.any():
                continue
            for name, df in (
                ("Pressures", pressures),
                ("Levels", levels),
                ("Demands", demands),
                ("Flows", flows),
                ("Leaks", leaks_df),
            ):
                path = out_dir / f"{year}_SCADA_{name}.csv"
                sub = df.loc[mask.values]
                sub.to_csv(path, index=False)
                written[path.name] = {
                    "rows": int(len(sub)),
                    "cols": int(sub.shape[1]),
                    "sha256": sha256_of(path),
                }
                print(f"  wrote {path.name}: {len(sub)} x {sub.shape[1]}", flush=True)

        meta_path = out_dir / "REGENERATION_METADATA.json"
        meta_path.write_text(
            json.dumps(
                {
                    "generated_utc": pd.Timestamp.now("UTC").isoformat(),
                    "source_generator": "data/raw/battledim_official/dataset_generator.py",
                    "source_generator_sha256": sha256_of(RAW / "dataset_generator.py"),
                    "network_inp": "data/raw/battledim_official/L-TOWN_v2_Real.inp",
                    "network_inp_sha256": sha256_of(RAW / "L-TOWN_v2_Real.inp"),
                    "config": "data/raw/battledim_official/dataset_configuration.yalm",
                    "config_sha256": sha256_of(RAW / "dataset_configuration.yalm"),
                    "mode_simulation": MODE_SIMULATION,
                    "n_leaks": self.number_of_leaks,
                    "n_timesteps": int(n),
                    "period": [str(self.time_stamp[0]), str(self.time_stamp[-1])],
                    "porting_delta": PORTING_DELTA,
                    "deterministic": "no RNG is used anywhere in this pipeline",
                    "wall_clock_s": round(time.time() - t0, 1),
                    "versions": {
                        "python": sys.version.split()[0],
                        "wntr": wntr.__version__,
                        "numpy": np.__version__,
                        "pandas": pd.__version__,
                    },
                    "leak_events": leak_meta,
                    "outputs": written,
                },
                indent=2,
            )
            + "\n"
        )
        print(f"[{time.time()-t0:7.1f}s] done -> {meta_path}", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(RAW / "dataset_configuration.yalm"))
    ap.add_argument("--inp", default=str(RAW / "L-TOWN_v2_Real.inp"))
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()

    LOGS.mkdir(parents=True, exist_ok=True)
    creator = LeakDatasetCreator(Path(args.config), Path(args.inp))
    print(
        f"period {creator.time_stamp[0]} -> {creator.time_stamp[-1]} "
        f"({len(creator.time_stamp)} steps), {creator.number_of_leaks} leaks",
        flush=True,
    )
    creator.run(Path(args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
