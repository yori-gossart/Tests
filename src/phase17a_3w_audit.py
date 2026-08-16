"""PHASE 17A -- Gate 0 audit of the official Petrobras 3W repository.

AUDIT ONLY. No hypothesis is tested, no model is fitted, no performance number
is produced. The script inventories what the data can and cannot support.

Rules carried in from the mission: only REAL instances count for the main
validation; simulated and hand-drawn instances may never be used to inflate n.
They are counted here so the separation is documented, then set aside.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "phase17a_3w"
TW = Path("/tmp/claude-0/-home-user-Tests/6cb7a48c-87d9-5b87-a56a-413674448e9d/"
          "scratchpad/tw/3W")
DATA = TW / "dataset"
TRANSIENT_OFFSET = 100          # from dataset.ini [EVENTS]


def source_of(name: str) -> str:
    if name.startswith("WELL-"):
        return "REAL"
    if name.startswith("SIMULATED"):
        return "SIMULATED"
    if name.startswith("DRAWN"):
        return "HAND-DRAWN"
    return "UNKNOWN"


def audit_instance(path: Path, event_type: int) -> dict:
    d = pd.read_parquet(path)
    cl = d["class"]
    n = len(d)
    idx = d.index

    lead_na = int((~cl.notna()).cumprod().sum()) if bool(cl.isna().iloc[0]) else 0
    labelled = cl.notna()

    # first observation carrying the event label, steady (k) or transient (100+k)
    is_event = labelled & (cl != 0)
    onset_pos = int(np.argmax(is_event.to_numpy())) if bool(is_event.any()) else -1

    # labelled-normal run immediately before onset
    pre_zero = 0
    if onset_pos > 0:
        # unlabelled observations are NOT normal: NA is treated as "unknown",
        # which is what breaks the run and is exactly the point being audited
        z = (cl.iloc[:onset_pos] == 0).fillna(False).to_numpy(dtype=bool)
        k = 0
        while k < len(z) and z[len(z) - 1 - k]:
            k += 1
        pre_zero = int(k)

    dt = pd.Series(idx).diff().dt.total_seconds().dropna()
    step = float(dt.median()) if len(dt) else float("nan")

    var_cols = [c for c in d.columns if c not in ("class", "state")]
    all_nan = [c for c in var_cols if bool(d[c].isna().all())]
    part_nan = {c: float(d[c].isna().mean()) for c in var_cols
                if 0 < d[c].isna().mean() < 1}

    labels = Counter({int(k): int(v) for k, v in cl.value_counts(dropna=True).items()})
    return {
        "path": str(path.relative_to(TW)),
        "file": path.name,
        "event_type": event_type,
        "source": source_of(path.name),
        "well": path.name.split("_")[0] if path.name.startswith("WELL-") else None,
        "n_obs": n,
        "step_seconds": step,
        "duration_s": float((idx[-1] - idx[0]).total_seconds()),
        "leading_unlabelled": lead_na,
        "n_unlabelled": int(cl.isna().sum()),
        "onset_pos": onset_pos,
        "pre_event_labelled_normal": pre_zero,
        "pre_event_total": (onset_pos if onset_pos >= 0 else n),
        "has_transient": bool(any(k >= TRANSIENT_OFFSET for k in labels)),
        "labels": {str(k): v for k, v in sorted(labels.items())},
        "n_vars_all_nan": len(all_nan),
        "vars_all_nan": all_nan,
        "n_vars_partial_nan": len(part_nan),
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "logs").mkdir(exist_ok=True)

    inventory, rows = defaultdict(Counter), []
    wells_by_type = defaultdict(set)
    class_dirs = sorted([p for p in DATA.iterdir() if p.is_dir() and p.name.isdigit()],
                        key=lambda p: int(p.name))

    for cdir in class_dirs:
        et = int(cdir.name)
        for f in sorted(cdir.glob("*.parquet")):
            src = source_of(f.name)
            inventory[et][src] += 1
            if src == "REAL":
                wells_by_type[et].add(f.name.split("_")[0])
                rows.append(audit_instance(f, et))
        print(f"class {et}: {sum(inventory[et].values())} files "
              f"({inventory[et]['REAL']} real) audited", flush=True)

    df = pd.DataFrame(rows)
    df.to_csv(OUT / "REAL_INSTANCE_AUDIT.csv", index=False)

    inv = pd.DataFrame([
        {"event_type": et, "REAL": inventory[et]["REAL"],
         "SIMULATED": inventory[et]["SIMULATED"],
         "HAND_DRAWN": inventory[et]["HAND-DRAWN"],
         "TOTAL": sum(inventory[et].values()),
         "distinct_real_wells": len(wells_by_type[et])}
        for et in sorted(inventory)])
    inv.to_csv(OUT / "INSTANCE_INVENTORY.csv", index=False)

    anom = df[df.event_type != 0]
    per_type = (anom.groupby("event_type")
                .agg(n_real=("file", "size"),
                     n_wells=("well", "nunique"),
                     median_obs=("n_obs", "median"),
                     median_step_s=("step_seconds", "median"),
                     median_leading_unlabelled=("leading_unlabelled", "median"),
                     median_pre_event_total=("pre_event_total", "median"),
                     median_pre_event_labelled_normal=("pre_event_labelled_normal", "median"),
                     frac_with_transient=("has_transient", "mean"),
                     frac_no_onset=("onset_pos", lambda s: float((s < 0).mean())),
                     median_vars_all_nan=("n_vars_all_nan", "median"))
                .reset_index())
    per_type.to_csv(OUT / "REAL_PER_EVENT_TYPE.csv", index=False)

    # channel availability across REAL anomalous instances
    var_cols = sorted({v for lst in anom.vars_all_nan for v in lst})
    avail = []
    for v in var_cols:
        miss = float(np.mean([v in lst for lst in anom.vars_all_nan]))
        avail.append({"variable": v, "frac_instances_entirely_missing": miss})
    avail_df = pd.DataFrame(avail).sort_values("frac_instances_entirely_missing",
                                               ascending=False)
    avail_df.to_csv(OUT / "CHANNEL_AVAILABILITY.csv", index=False)

    # well-level structure: the only leakage-free split unit
    well_type = (anom.groupby(["well", "event_type"]).size()
                 .rename("n_instances").reset_index())
    well_type.to_csv(OUT / "WELL_BY_EVENT_TYPE.csv", index=False)

    summary = {
        "repository": "https://github.com/petrobras/3W",
        "commit": "93793db1dbd8b672f87f9259bedc913eb8c13683",
        "dataset_version": "2.0.0",
        "clone_size": "5.3 GB",
        "totals": {
            "instances": int(inv.TOTAL.sum()),
            "REAL": int(inv.REAL.sum()),
            "SIMULATED": int(inv.SIMULATED.sum()),
            "HAND_DRAWN": int(inv.HAND_DRAWN.sum()),
            "REAL_normal_class0": int(inv[inv.event_type == 0].REAL.iloc[0]),
            "REAL_anomalous": int(inv[inv.event_type != 0].REAL.sum()),
            "distinct_real_wells": int(anom.well.nunique()),
        },
        "folds_directory_present": (DATA / "folds").exists(),
        "transient_offset": TRANSIENT_OFFSET,
    }
    (OUT / "AUDIT_SUMMARY.json").write_text(json.dumps(summary, indent=2))
    print("\n" + json.dumps(summary, indent=2))
    print("\n--- per event type (REAL, anomalous) ---")
    print(per_type.to_string(index=False))
    print("\n--- channel availability (entirely missing) ---")
    print(avail_df.head(15).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
