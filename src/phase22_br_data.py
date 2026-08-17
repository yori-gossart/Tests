"""PHASE 22-BR -- loaders, materialised splits and class verification (commit B).

Executes section 4 of PROTOCOLE_PHASE22_BR.md. NO model, NO score, NO endpoint.
This module is also imported by the results stage so that the data handling is
provably identical between the gate and the confirmatory run.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "phase22_br"
WORK = Path("/tmp/claude-0/-home-user-Tests/6cb7a48c-87d9-5b87-a56a-413674448e9d/"
            "scratchpad/p22")

SEED = 22260822
GAS_TRAIN_BATCHES = [1, 2, 3, 4]
GAS_CALIB_BATCHES = [5, 6]
GAS_TEST_BATCHES = [7, 8, 9, 10]


def _root(acc: dict) -> Path:
    return WORK / acc["repo"].replace("/", "__")


def load_gas(acc: dict):
    root = _root(acc)
    Xs, ys, bs = [], [], []
    for i in range(1, 11):
        p = root / acc["found"][f"batch{i}"]
        for line in p.read_text(errors="ignore").splitlines():
            line = line.strip()
            if not line:
                continue
            toks = line.split()
            ys.append(int(toks[0].split(";")[0]))
            v = np.zeros(128, dtype=np.float64)
            for t in toks[1:]:
                k, val = t.split(":")
                v[int(k) - 1] = float(val)
            Xs.append(v)
            bs.append(i)
    return np.asarray(Xs), np.asarray(ys), np.asarray(bs)


def load_credit(acc: dict):
    root = _root(acc)
    d = pd.read_csv(root / acc["found"]["data"], low_memory=False)
    tgt = acc["found"]["target_col"]
    y = d[tgt].to_numpy()
    drop = [tgt] + [c for c in d.columns if str(c).strip().upper() == "ID"]
    X = d.drop(columns=drop).to_numpy(dtype=float)
    return X, y, None


def load_drybean(acc: dict):
    root = _root(acc)
    d = pd.read_excel(root / acc["found"]["data"])
    y = d.iloc[:, -1].astype(str).str.strip().str.upper().to_numpy()
    X = d.iloc[:, :-1].to_numpy(dtype=float)
    return X, y, None


LOADERS = {"GAS": load_gas, "CREDIT": load_credit, "DRYBEAN": load_drybean}


def stratified_split(y: np.ndarray) -> np.ndarray:
    """60/20/20 stratified by class, frozen seed."""
    rng = np.random.default_rng(SEED)
    split = np.empty(len(y), dtype=object)
    for c in np.unique(y):
        idx = rng.permutation(np.flatnonzero(y == c))
        n = len(idx)
        a, b = int(round(0.6 * n)), int(round(0.8 * n))
        split[idx[:a]] = "train"
        split[idx[a:b]] = "calib"
        split[idx[b:]] = "test"
    return split


def gas_shift_split(batch: np.ndarray) -> np.ndarray:
    """NATURAL_TEMPORAL_SHIFT, batch ranges frozen in the protocol."""
    split = np.empty(len(batch), dtype=object)
    split[np.isin(batch, GAS_TRAIN_BATCHES)] = "train"
    split[np.isin(batch, GAS_CALIB_BATCHES)] = "calib"
    split[np.isin(batch, GAS_TEST_BATCHES)] = "test"
    return split


def main() -> int:
    gate = json.load(open(OUT / "GATE_B.json"))
    rep = {"protocol_sha256": gate["protocol_sha256"], "splits": {}}
    for ds in ("GAS", "CREDIT", "DRYBEAN"):
        g = gate["datasets"][ds]
        if g["status"] != "EXECUTABLE":
            rep["splits"][ds] = {"status": g["status"]}
            continue
        X, y, batch = LOADERS[ds](g["accepted"])
        sp = stratified_split(y)
        classes = sorted(set(map(str, np.unique(y))))
        per = {s: {str(k): int(v) for k, v in
                   pd.Series(y[sp == s]).value_counts().sort_index().items()}
               for s in ("train", "calib", "test")}
        allc = all(len(per[s]) == len(classes) for s in per)
        df = pd.DataFrame({"y": y, "split": sp})
        if batch is not None:
            df["batch"] = batch
        df.to_csv(OUT / f"SPLIT_{ds}.csv", index=False)
        entry = {"status": "EXECUTABLE", "shape": list(X.shape),
                 "n_classes": len(classes), "classes": classes,
                 "split_counts": {s: int((sp == s).sum()) for s in
                                  ("train", "calib", "test")},
                 "class_counts_per_split": per,
                 "all_classes_present_in_every_split": bool(allc),
                 "n_nan": int(np.isnan(X).sum())}
        print(f"{ds}: X{X.shape} classes={len(classes)} "
              f"split={entry['split_counts']} toutes classes partout={allc}", flush=True)

        if ds == "GAS":
            ssp = gas_shift_split(batch)
            sper = {s: {str(k): int(v) for k, v in
                        pd.Series(y[ssp == s]).value_counts().sort_index().items()}
                    for s in ("train", "calib", "test")}
            sok = all(len(sper[s]) == len(classes) for s in sper)
            pd.DataFrame({"y": y, "split": ssp, "batch": batch}).to_csv(
                OUT / "SPLIT_GAS_NATURAL_SHIFT.csv", index=False)
            entry["natural_temporal_shift"] = {
                "train_batches": GAS_TRAIN_BATCHES, "calib_batches": GAS_CALIB_BATCHES,
                "test_batches": GAS_TEST_BATCHES,
                "split_counts": {s: int((ssp == s).sum()) for s in
                                 ("train", "calib", "test")},
                "class_counts_per_split": sper,
                "all_6_classes_present_in_every_split": bool(sok),
                "status": "EXECUTABLE" if sok else "NOT_EXECUTABLE",
                "reason": "" if sok else "au moins une classe absente d'une des trois "
                                         "parties ; aucun changement de decoupage n'est "
                                         "effectue (protocole 4.3)"}
            print(f"  shift: {entry['natural_temporal_shift']['split_counts']} "
                  f"6 classes partout={sok} -> "
                  f"{entry['natural_temporal_shift']['status']}", flush=True)
        rep["splits"][ds] = entry

    json.dump(rep, open(OUT / "VERIFY_SPLITS.json", "w"), indent=2)
    print("\n=== VERIFICATION ECRITE ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
