"""
Build the leak-sensitivity library for L-Town.

For every candidate leak scenario z (a leak of reference size at one junction)
we record the pressure deviation it induces at every candidate sensor location,
across a set of operating snapshots:

    Delta p[z, j, t] = p_j^nominal(t) - p_j^leak(z)(t)          [m]

This tensor is the common substrate for ALL sensor-selection methods compared in
this study (FO and every OED / centrality / random baseline). It is computed on
the nominal model L-TOWN_v2_Model.inp -- the model a utility would actually have
-- and never on the 'real' network or on any 2019 quantity.

LEAK MODEL
----------
The BattLeDIM generator represents a leak as an orifice discharge

    q = Cd * A * sqrt(2 g p),   Cd = 0.75,   A = pi (d/2)^2

This is exactly an EPANET emitter with exponent 0.5 and coefficient

    C = Cd * sqrt(2 g) * A = 3.3221 * A                    [m^3/s / m^0.5]

expressed in wntr's internal SI units (wntr converts to the model's CMH flow
units when it writes the [EMITTERS] section). verify_emitter_equivalence()
checks this against wntr's own add_leak() model so the claim is tested rather
than asserted.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import wntr
import yaml

REPO = Path(__file__).resolve().parents[1]
RAW = REPO / "data" / "raw" / "battledim_official"
PROC = REPO / "data" / "processed"

G = 9.81
CD = 0.75
EMITTER_C_PER_AREA = CD * np.sqrt(2.0 * G)  # 3.3221 (m^3/s) / (m^2 * m^0.5), wntr SI
CMH = 3600.0  # m^3/s -> m^3/h


def area_of(diameter_m: float) -> float:
    return 3.14159 * (diameter_m / 2.0) ** 2


def load_config(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="latin-1"))


def leak_table(cfg: dict) -> list[dict]:
    rows = []
    for raw in cfg["leakages"][1:]:
        parts = [p.strip() for p in str(raw).split(",")]
        if len(parts) < 6:
            continue
        rows.append(
            {
                "linkID": parts[0],
                "start": parts[1],
                "end": parts[2],
                "diameter_m": float(parts[3]),
                "type": parts[4],
                "peak": parts[5],
            }
        )
    return rows


def verify_emitter_equivalence(inp: Path, node_id: str, diameter_m: float) -> dict:
    """Check the EPANET-emitter leak against wntr's add_leak on the same node."""
    area = area_of(diameter_m)

    wn = wntr.network.WaterNetworkModel(str(inp))
    wn.options.time.duration = 6 * 3600
    node = wn.get_node(node_id)
    node.add_leak(wn, discharge_coeff=CD, area=area, start_time=0, end_time=6 * 3600)
    res_wntr = wntr.sim.WNTRSimulator(wn).run_sim()
    q_wntr = res_wntr.node["leak_demand"][node_id].values * 3600.0  # m3/s -> CMH

    # EPANET reports emitter outflow inside nodal demand, so difference it
    # against the same run without the emitter to isolate the leak flow.
    wn_ref = wntr.network.WaterNetworkModel(str(inp))
    wn_ref.options.time.duration = 6 * 3600
    d_ref = wntr.sim.EpanetSimulator(wn_ref).run_sim().node["demand"][node_id].values

    wn2 = wntr.network.WaterNetworkModel(str(inp))
    wn2.options.time.duration = 6 * 3600
    wn2.get_node(node_id).emitter_coefficient = EMITTER_C_PER_AREA * area
    d_leak = wntr.sim.EpanetSimulator(wn2).run_sim().node["demand"][node_id].values
    m = min(len(d_ref), len(d_leak))
    q_ep = (d_leak[:m] - d_ref[:m]) * CMH  # m^3/s -> CMH

    # Drop the final step: add_leak's end_time deactivates the wntr leak there,
    # while the EPANET emitter stays on, so the two models are not comparable at
    # that single boundary sample.
    n = min(len(q_wntr), len(q_ep)) - 1
    a, b = q_wntr[:n], q_ep[:n]
    denom = np.maximum(np.abs(a).mean(), 1e-9)
    return {
        "node": node_id,
        "diameter_m": diameter_m,
        "emitter_coefficient_si": EMITTER_C_PER_AREA * area,
        "n_compared_steps": int(n),
        "mean_leak_flow_wntr_cmh": float(a.mean()),
        "mean_leak_flow_epanet_cmh": float(b.mean()),
        "max_abs_rel_diff": float(np.abs(a - b).max() / denom),
    }


def build_library(
    inp: Path,
    sensors: list[str],
    diameter_m: float,
    snapshot_stride: int,
    horizon_s: int,
    out_path: Path,
    limit: int | None = None,
) -> dict:
    """Simulate one leak per junction and record sensor pressure deviations."""
    t0 = time.time()
    base = wntr.network.WaterNetworkModel(str(inp))
    base.options.time.duration = horizon_s
    junctions = list(base.junction_name_list)
    if limit:
        junctions = junctions[:limit]

    res0 = wntr.sim.EpanetSimulator(base).run_sim()
    p0_all = res0.node["pressure"]
    times = np.asarray(p0_all.index)[::snapshot_stride]
    p0 = p0_all.loc[::snapshot_stride, sensors].to_numpy(dtype=np.float64)  # (T, J)

    area = area_of(diameter_m)
    coeff = EMITTER_C_PER_AREA * area

    T, J = p0.shape
    delta = np.zeros((len(junctions), J, T), dtype=np.float32)
    leak_flow = np.zeros((len(junctions), T), dtype=np.float32)
    failed: list[str] = []

    for i, jid in enumerate(junctions):
        wn = wntr.network.WaterNetworkModel(str(inp))
        wn.options.time.duration = horizon_s
        wn.get_node(jid).emitter_coefficient = coeff
        try:
            res = wntr.sim.EpanetSimulator(wn).run_sim()
        except Exception:
            failed.append(jid)
            continue
        pk = res.node["pressure"].loc[::snapshot_stride, sensors].to_numpy(dtype=np.float64)
        m = min(T, pk.shape[0])
        delta[i, :, :m] = (p0[:m] - pk[:m]).T
        pl = res.node["pressure"].loc[::snapshot_stride, jid].to_numpy(dtype=np.float64)[:m]
        leak_flow[i, :m] = coeff * np.sqrt(np.clip(pl, 0, None)) * CMH

        if (i + 1) % 100 == 0:
            print(f"  {i+1}/{len(junctions)} scenarios  ({time.time()-t0:.0f}s)", flush=True)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        out_path,
        delta=delta,
        leak_flow_cmh=leak_flow,
        scenarios=np.array(junctions),
        sensors=np.array(sensors),
        times_s=np.asarray(times, dtype=np.float64),
        diameter_m=diameter_m,
    )

    meta = {
        "inp": str(inp.relative_to(REPO)),
        "n_scenarios": len(junctions),
        "n_sensors": len(sensors),
        "n_snapshots": int(T),
        "reference_diameter_m": diameter_m,
        "emitter_coefficient_cmh_per_sqrt_m": coeff,
        "horizon_s": horizon_s,
        "snapshot_stride": snapshot_stride,
        "failed_scenarios": failed,
        "wall_clock_s": round(time.time() - t0, 1),
        "output": str(out_path.relative_to(REPO)),
    }
    print(json.dumps(meta, indent=2), flush=True)
    return meta


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inp", default=str(RAW / "L-TOWN_v2_Model.inp"))
    ap.add_argument("--config", default=str(RAW / "dataset_configuration_historical.yalm"),
                    help="2018 configuration ONLY -- fixes the reference leak size")
    ap.add_argument("--horizon-hours", type=int, default=168)
    ap.add_argument("--snapshot-stride", type=int, default=24, help="24 x 5min = 2 h")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--out", default=str(PROC / "sensitivity_library.npz"))
    ap.add_argument("--verify-only", action="store_true")
    ap.add_argument("--all-junctions", action="store_true",
                    help="record Delta p at EVERY junction, not only the 33 "
                         "pre-installed BattLeDIM sensors, so selection over the "
                         "full candidate set can be studied")
    args = ap.parse_args()

    cfg = load_config(Path(args.config))
    sensors = [str(s) for s in cfg["pressure_sensors"]]
    if args.all_junctions:
        import wntr as _w
        sensors = list(_w.network.WaterNetworkModel(str(args.inp)).junction_name_list)
        print(f"ALL-JUNCTIONS mode: {len(sensors)} candidate sensor locations", flush=True)
    leaks_2018 = leak_table(cfg)
    diameters = np.array([r["diameter_m"] for r in leaks_2018])
    d_ref = float(np.median(diameters))
    print(
        f"reference leak diameter = median of the {len(diameters)} 2018 events "
        f"= {d_ref:.6f} m (range {diameters.min():.6f}-{diameters.max():.6f})",
        flush=True,
    )

    check = verify_emitter_equivalence(Path(args.inp), sensors[0], d_ref)
    print("emitter/add_leak equivalence check:", json.dumps(check, indent=2), flush=True)
    if args.verify_only:
        return 0
    if check["max_abs_rel_diff"] > 0.02:
        raise SystemExit(
            f"emitter model disagrees with wntr add_leak by "
            f"{check['max_abs_rel_diff']:.3%} -- refusing to build the library"
        )

    build_library(
        inp=Path(args.inp),
        sensors=sensors,
        diameter_m=d_ref,
        snapshot_stride=args.snapshot_stride,
        horizon_s=args.horizon_hours * 3600,
        out_path=Path(args.out),
        limit=args.limit,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
