"""PHASE 15 -- exploratory feature table over the EXISTING Phase 14 data.

No new simulation. fo_metrics.py is imported unmodified; every standard metric
comes from tep_metrics.py, which does not import it.

Outcome labels. The failure label is "the independent RandomForest gets the
fault wrong". For VALID and TEST the forest is fit on TRAIN, as in Phase 14. For
TRAIN itself an in-sample forest would be perfect and the label degenerate, so
TRAIN labels are CROSS-FITTED with 5 folds grouped by seed -- the same estimator,
never seeing the realisation it labels. That is what makes TRAIN usable for
fitting models without leaking the outcome.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import GroupKFold

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fo_metrics
import tep_metrics as TM

REPO = Path(__file__).resolve().parents[1]
P14 = REPO / "phase14_tep"
OUT = REPO / "phase15_tep"
PROTO = json.loads((P14 / "PROTOCOLE_PREENREGISTRE_TEP.json").read_text())
GEN = Path("/tmp/claude-0/-home-user-Tests/6cb7a48c-87d9-5b87-a56a-413674448e9d/scratchpad/tep/gen")
TEPSRC = Path("/tmp/claude-0/-home-user-Tests/6cb7a48c-87d9-5b87-a56a-413674448e9d/"
              "scratchpad/tep/tennessee-eastman-profBraatz")

FAULTS = PROTO["disturbances"]["ids"]
KAPPA, ETA = PROTO["fo_inputs"]["kappa"], PROTO["fo_inputs"]["eta"]
SIZES = PROTO["sensor_designs"]["design_sizes"]
N_DESIGNS = PROTO["sensor_designs"]["designs_per_size"]
DESIGN_SEED = 20260816
SPLITS = {"train": list(range(0, 25)), "val": list(range(25, 35)), "test": list(range(35, 50))}


def load_sigma() -> np.ndarray:
    import re
    return np.asarray([float(m.group(2)) for m in re.finditer(
        r"XNS\((\d+)\)=([0-9.]+)D0", (TEPSRC / "teprob.f").read_text())])


def load_bank(path: Path) -> dict:
    z = np.load(path)
    return {tuple(int(x) for x in k.split("_")): z[k] for k in z.files}


def frozen_designs() -> list[dict]:
    rng = np.random.default_rng(DESIGN_SEED)
    out = []
    for size in SIZES:
        for rep in range(N_DESIGNS):
            out.append({"design_id": len(out), "size": size, "rep": rep,
                        "channels": sorted(rng.choice(41, size=size, replace=False).tolist())})
    return out


def build(bank: dict, seed_idx: list[int]):
    d, obs, yf, ys, nrm = [], [], [], [], []
    for si in seed_idx:
        base = bank[(0, si)].astype(np.float64)
        nrm.append(base)
        for k in FAULTS:
            f = bank[(k, si)].astype(np.float64)
            d.append(f - base); obs.append(f); yf.append(k); ys.append(si)
    return (np.stack(d), np.stack(obs), np.asarray(yf), np.asarray(ys), np.stack(nrm))


def rf_features(obs: np.ndarray, ch: list[int]) -> np.ndarray:
    x = obs[:, ch, :]
    return np.concatenate([x.mean(2), x.std(2), x.min(2), x.max(2), x[:, :, -1]], axis=1)


def rf_outputs(proba, classes, y):
    pred = classes[proba.argmax(axis=1)]
    order = np.argsort(-proba, axis=1)
    rank = np.array([int(np.flatnonzero(classes[order[i]] == y[i])[0]) + 1 for i in range(len(y))])
    p_true = np.array([proba[i, np.flatnonzero(classes == y[i])[0]] for i in range(len(y))])
    srt = np.sort(proba, axis=1)[:, ::-1]
    with np.errstate(divide="ignore"):
        ent = -(proba * np.log(np.maximum(proba, 1e-300))).sum(axis=1)
    return {"top1_correct": (pred == y).astype(int), "failure": (pred != y).astype(int),
            "rank_true": rank, "posterior_true": p_true,
            "log_loss": -np.log(np.maximum(p_true, 1e-300)),
            "rf_entropy": ent, "rf_margin": srt[:, 0] - srt[:, 1]}


def main() -> int:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "logs").mkdir(exist_ok=True)
    sigma = load_sigma()
    bank = load_bank(GEN / "nominal.npz")
    designs = frozen_designs()

    data = {}
    for name, idx in SPLITS.items():
        d, obs, yf, ys, nrm = build(bank, idx)
        W = TM.whiten(d, sigma)
        data[name] = {"delta": d, "obs": obs, "y": yf, "seed": ys, "W": W,
                      "v": TM.per_channel_visibility(W), "m": TM.mean_profile(W),
                      "Sf": TM.scenario_covariance(W), "normal": nrm}
        print(f"{name}: {len(yf)} realisations  ({time.time()-t0:.0f}s)", flush=True)

    # null covariance and fault centroids -- TRAIN ONLY
    Wn = TM.whiten(data["train"]["normal"], sigma)
    Sn = TM.null_covariance(Wn)
    centroids = TM.fault_centroids(data["train"]["m"], data["train"]["y"], FAULTS)
    np.save(OUT / "null_covariance.npy", Sn)
    print(f"Sigma_n estimated on {len(Wn)} TRAIN normal runs, cond={np.linalg.cond(Sn):.1f}",
          flush=True)

    # frozen FO support, TRAIN, nominal noise -- identical to Phase 14
    support = fo_metrics.freeze_support(data["train"]["delta"], sigma, KAPPA)
    print(f"E* = {support.size}/{len(data['train']['y'])}", flush=True)

    rows = []
    for di, dd in enumerate(designs):
        ch = dd["channels"]

        rf_full = RandomForestClassifier(n_estimators=500, random_state=DESIGN_SEED, n_jobs=-1)
        Xtr = rf_features(data["train"]["obs"], ch)
        rf_full.fit(Xtr, data["train"]["y"])

        # cross-fitted TRAIN posteriors, folds grouped by SEED
        proba_tr = np.zeros((len(data["train"]["y"]), len(FAULTS)))
        gkf = GroupKFold(n_splits=5)
        for tr_i, te_i in gkf.split(Xtr, data["train"]["y"], groups=data["train"]["seed"]):
            m = RandomForestClassifier(n_estimators=500, random_state=DESIGN_SEED, n_jobs=-1)
            m.fit(Xtr[tr_i], data["train"]["y"][tr_i])
            proba_tr[te_i] = m.predict_proba(Xtr[te_i])

        for split in ("train", "val", "test"):
            D = data[split]
            proba = proba_tr if split == "train" else rf_full.predict_proba(
                rf_features(D["obs"], ch))
            classes = rf_full.classes_

            vis = TM.visibility_metrics(D["W"], D["v"], D["m"], D["Sf"], Sn, ch)
            iso = TM.isolability_metrics(D["m"], D["y"], centroids, Sn, ch)
            fo_vis = fo_metrics.visibility(D["delta"], sigma)      # unmodified FO
            fo_d_S = fo_vis[:, ch].max(axis=1)

            rec = {"design_id": di, "design_size": dd["size"], "design_rep": dd["rep"],
                   "split": split, "fault": D["y"], "seed_idx": D["seed"],
                   "fo_d_S": fo_d_S}
            rec.update(vis); rec.update(iso); rec.update(rf_outputs(proba, classes, D["y"]))
            rows.append(pd.DataFrame(rec))

        if (di + 1) % 10 == 0:
            print(f"  {di+1}/{len(designs)} designs  ({time.time()-t0:.0f}s)", flush=True)

    ev = pd.concat(rows, ignore_index=True)
    ev.to_csv(OUT / "FEATURES_PHASE15.csv.gz", index=False, compression="gzip")
    np.save(OUT / "support_mask_train.npy", support.mask)
    print(f"wrote {len(ev)} rows in {time.time()-t0:.0f}s", flush=True)

    ident = float(np.abs(ev.fo_d_S - ev.max_abs).max())
    print(f"CHECK  max |fo_d_S - max_abs| = {ident:.3e}  "
          f"(they are the same statistic by definition)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
