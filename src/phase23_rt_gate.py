"""PHASE 23-RT -- data gate (commit B).

Executes sections 3 to 7 of PROTOCOLE_PHASE23_RT.md
(SHA-256 524ebbb7e61f516d18bd4ddafbb4bed9bfc583cfefe54623a85cf0a838bcffcd,
frozen at commit e531cd7 before any TEST access).

Builds the historical exclusion inventory, applies the frozen blind selection
rule, acquires the retained datasets, materialises the splits and verifies the
classes. NO model is fitted, NO score is computed, NO TEST metric is produced.

TEST_OPENED: NO
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "phase23_rt"
WORK = Path("/tmp/claude-0/-home-user-Tests/6cb7a48c-87d9-5b87-a56a-413674448e9d/"
            "scratchpad/p23")

SEED = 23260823
MANIFEST = ("https://raw.githubusercontent.com/EpistasisLab/pmlb/master/pmlb/"
            "all_summary_stats.tsv")
DATA_URL = ("https://media.githubusercontent.com/media/EpistasisLab/pmlb/master/"
            "datasets/{name}/{name}.tsv.gz")   # LFS media endpoint: raw.* serves the
            # LFS pointer, not the payload

MANDATED_TOKENS = ["credit", "gas", "bean", "sensorless", "zema"]
REPO_TOKENS = ["secom", "steel", "scania", "aps", "tennessee", "eastman", "leak",
               "epanet", "3w", "digit", "hydraulic"]
WORD_TOKENS = ["har"]          # applied as a whole word only

MIN_N, MAX_N = 1000, 100000
MIN_P, MAX_P = 5, 500
MIN_CLASS = 50
TARGET_DATASETS = 4
MIN_DATASETS = 3
ID_UNIQUE_FRAC = 0.95


def sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def fetch(url: str, timeout: int = 180) -> bytes | None:
    r = subprocess.run(["curl", "-sSL", "--max-time", str(timeout), url],
                       capture_output=True)
    return r.stdout if r.returncode == 0 and r.stdout else None


def historical_inventory() -> dict:
    """Scan every previous phase directory and src/ for dataset mentions."""
    pat = re.compile("|".join(MANDATED_TOKENS + REPO_TOKENS + [r"\bhar\b"]), re.I)
    hits: dict[str, set] = {}
    for p in list(REPO.glob("phase*/**/*")) + list(REPO.glob("src/*")):
        if not p.is_file() or p.suffix not in (".md", ".py", ".json", ".txt", ".csv"):
            continue
        if p.is_relative_to(OUT):
            continue
        try:
            txt = p.read_text(errors="ignore")
        except Exception:
            continue
        for m in pat.findall(txt):
            hits.setdefault(m.lower(), set()).add(str(p.relative_to(REPO)))
    return {"tokens_found": {k: sorted(v)[:6] for k, v in sorted(hits.items())},
            "n_tokens": len(hits),
            "mandated": ["CREDIT", "GAS", "DRYBEAN", "SENSORLESS", "HAR", "ZeMA"],
            "from_repo_scan": ["SECOM", "STEEL", "SCANIA/APS", "TENNESSEE/TEP",
                               "LEAKDB", "EPANET", "3W", "DIGITS", "HYDRAULIC"],
            "exclusion_tokens": MANDATED_TOKENS + REPO_TOKENS,
            "exclusion_word_tokens": WORD_TOKENS}


def excluded(name: str) -> str | None:
    n = name.lower()
    for t in MANDATED_TOKENS + REPO_TOKENS:
        if t in n:
            return f"jeton d'exclusion historique '{t}'"
    for t in WORD_TOKENS:
        if re.search(rf"\b{t}\b", n):
            return f"jeton d'exclusion historique (mot entier) '{t}'"
    return None


def stratified_split(y: np.ndarray) -> np.ndarray:
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


def try_dataset(name: str) -> dict:
    """Acquire and check one candidate. No model, no TEST metric."""
    raw = fetch(DATA_URL.format(name=name))
    if raw is None:
        return {"status": "NOT_EXECUTABLE", "reason": "telechargement impossible"}
    try:
        d = pd.read_csv(io.BytesIO(raw), sep="\t", compression="gzip")
    except Exception as e:
        return {"status": "NOT_EXECUTABLE", "reason": f"illisible: {e}"}
    if "target" not in d.columns:
        return {"status": "NOT_EXECUTABLE", "reason": "colonne 'target' absente"}
    y = d["target"].to_numpy()
    Xd = d.drop(columns=["target"])
    dropped_id = [c for c in Xd.columns
                  if Xd[c].nunique(dropna=False) >= ID_UNIQUE_FRAC * len(Xd)]
    if dropped_id:
        Xd = Xd.drop(columns=dropped_id)
    obj = [c for c in Xd.columns if Xd[c].dtype == object]
    if obj:
        return {"status": "NOT_EXECUTABLE",
                "reason": f"{len(obj)} colonne(s) non numeriques / texte libre"}
    n, p = Xd.shape
    vc = pd.Series(y).value_counts()
    checks = {"n_instances": int(n), "n_features_usable": int(p),
              "n_classes": int(len(vc)), "min_class_count": int(vc.min()),
              "dropped_quasi_identifiers": dropped_id}
    fails = []
    if not (MIN_N <= n <= MAX_N):
        fails.append(f"n={n} hors [{MIN_N}, {MAX_N}]")
    if not (MIN_P <= p <= MAX_P):
        fails.append(f"p={p} hors [{MIN_P}, {MAX_P}]")
    if len(vc) < 2:
        fails.append("moins de 2 classes")
    if vc.min() < MIN_CLASS:
        fails.append(f"plus petite classe = {vc.min()} < {MIN_CLASS}")
    if fails:
        return {"status": "NOT_ELIGIBLE", "reason": "; ".join(fails), **checks}
    sp = stratified_split(y)
    per = {s: {str(k): int(v) for k, v in
               pd.Series(y[sp == s]).value_counts().sort_index().items()}
           for s in ("train", "calib", "test")}
    allc = all(len(per[s]) == len(vc) for s in per)
    overlap = (len(np.unique(np.flatnonzero(sp == "train"))) +
               len(np.flatnonzero(sp == "calib")) +
               len(np.flatnonzero(sp == "test"))) == n
    return {"status": "EXECUTABLE", **checks,
            "sha256_tsv_gz": sha_bytes(raw), "n_bytes": len(raw),
            "class_distribution": {str(k): int(v) for k, v in vc.sort_index().items()},
            "n_nan": int(Xd.isna().sum().sum()),
            "split_counts": {s: int((sp == s).sum()) for s in ("train", "calib", "test")},
            "class_counts_per_split": per,
            "all_classes_present_in_every_split": bool(allc),
            "splits_partition_exactly": bool(overlap),
            "_X": Xd, "_y": y, "_split": sp}


def main() -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    (OUT / "logs").mkdir(parents=True, exist_ok=True)

    hist = historical_inventory()
    json.dump(hist, open(OUT / "EXCLUSION_HISTORIQUE.json", "w"), indent=2)
    print(f"inventaire historique: {hist['n_tokens']} jetons trouves dans le depot",
          flush=True)

    man = fetch(MANIFEST)
    if man is None:
        print("MANIFESTE INATTEIGNABLE", flush=True)
        return 1
    m = pd.read_csv(io.BytesIO(man), sep="\t")
    man_sha = sha_bytes(man)
    clf = m[m.task == "classification"].copy()
    print(f"manifeste PMLB: {len(m)} jeux, {len(clf)} en classification, "
          f"sha256={man_sha[:16]}...", flush=True)

    # ---- steps 2 and 3 of the frozen selection rule, on manifest metadata
    rows = []
    for r in clf.itertuples():
        why = excluded(r.dataset)
        if why:
            rows.append({"dataset": r.dataset, "stage": "exclu_historique",
                         "reason": why})
            continue
        f = []
        if not (MIN_N <= r.n_instances <= MAX_N):
            f.append(f"n={r.n_instances} hors [{MIN_N}, {MAX_N}]")
        if not (MIN_P <= r.n_features <= MAX_P):
            f.append(f"p={r.n_features} hors [{MIN_P}, {MAX_P}]")
        if r.n_classes < 2:
            f.append("moins de 2 classes")
        rows.append({"dataset": r.dataset,
                     "stage": "candidat" if not f else "inelig_manifeste",
                     "reason": "; ".join(f),
                     "n_instances": int(r.n_instances),
                     "n_features": int(r.n_features),
                     "n_classes": int(r.n_classes)})
    screen = pd.DataFrame(rows)
    cand0 = sorted(screen[screen.stage == "candidat"].dataset.tolist())

    # ---- AMENDEMENT 1: family dedup, _deprecated_*, mfeat_* -- names only
    cand, seen, amend_drop = [], set(), []
    for name in cand0:
        if name.startswith("_deprecated"):
            amend_drop.append({"dataset": name, "reason": "amendement 1: _deprecated_*"})
            continue
        if name.lower().startswith("mfeat"):
            amend_drop.append({"dataset": name,
                               "reason": "amendement 1: mfeat_* (UCI Multiple Features, "
                                         "meme source que digits Phase 13A)"})
            continue
        fam = name.split("_")[0].lower()
        if fam in seen:
            amend_drop.append({"dataset": name,
                               "reason": f"amendement 1: famille '{fam}' deja representee"})
            continue
        seen.add(fam)
        cand.append(name)
    for r in amend_drop:
        screen.loc[screen.dataset == r["dataset"], "stage"] = "exclu_amendement1"
        screen.loc[screen.dataset == r["dataset"], "reason"] = r["reason"]
    screen.to_csv(OUT / "CANDIDATE_SCREENING.csv", index=False)
    print(f"apres exclusions + eligibilite manifeste: {len(cand0)} candidats ; "
          f"apres amendement 1: {len(cand)}", flush=True)
    print(f"20 premiers dans l'ordre lexicographique gele: {cand[:20]}", flush=True)

    # ---- steps 4 to 6: walk the deterministic order, keep the first 4 executable
    retained, trail = {}, []
    for name in cand:
        if len(retained) >= TARGET_DATASETS:
            break
        res = try_dataset(name)
        st = res["status"]
        entry = {"dataset": name, "status": st,
                 **{k: v for k, v in res.items()
                    if not k.startswith("_") and k != "status"}}
        entry.pop("class_counts_per_split", None)
        trail.append(entry)
        print(f"  {name:28s} {st}"
              + (f"  ({res.get('reason','')})" if st != "EXECUTABLE" else
                 f"  n={res['n_instances']} p={res['n_features_usable']} "
                 f"K={res['n_classes']} min_class={res['min_class_count']}"),
              flush=True)
        if st == "EXECUTABLE":
            retained[name] = res

    report = {"protocol_sha256": (OUT / "PROTOCOL_SHA256.txt").read_text().split()[0],
              "TEST_OPENED": "NO",
              "source_pool_requested": "OpenML-CC18 (inatteignable, cf. protocole par. 2)",
              "source_pool_used": "PMLB",
              "manifest_url": MANIFEST, "manifest_sha256": man_sha,
              "n_classification_datasets_in_pool": int(len(clf)),
              "n_excluded_historical": int((screen.stage == "exclu_historique").sum()),
              "n_ineligible_manifest": int((screen.stage == "inelig_manifeste").sum()),
              "n_excluded_amendment1": int((screen.stage == "exclu_amendement1").sum()),
              "n_candidates_before_amendment1": len(cand0),
              "n_candidates": len(cand),
              "deterministic_order_first_20": cand[:20],
              "acquisition_trail": trail,
              "retained": {},
              "seed": SEED, "split": {"train": 0.6, "calib": 0.2, "test": 0.2}}

    for name, res in retained.items():
        X, y, sp = res["_X"], res["_y"], res["_split"]
        pd.DataFrame({"row": np.arange(len(y)), "y": y, "split": sp}).to_csv(
            OUT / f"SPLIT_{name}.csv", index=False)
        np.save(WORK / f"X_{name}.npy", X.to_numpy(dtype=float))
        np.save(WORK / f"y_{name}.npy", y)
        (WORK / f"cols_{name}.json").write_text(json.dumps(list(X.columns)))
        report["retained"][name] = {k: v for k, v in res.items()
                                    if not k.startswith("_")}

    n_ok = len(retained)
    report["n_retained"] = n_ok
    report["gate_status"] = ("OK" if n_ok >= MIN_DATASETS
                            else f"INCONCLUSIVE: {n_ok} < {MIN_DATASETS} jeux executables")
    json.dump(report, open(OUT / "DATA_GATE.json", "w"), indent=2, default=str)
    pd.DataFrame([{"dataset": k, "n": v["n_instances"], "p": v["n_features_usable"],
                   "K": v["n_classes"], "min_class": v["min_class_count"],
                   "sha256": v["sha256_tsv_gz"][:16] + "...",
                   **v["split_counts"]}
                  for k, v in report["retained"].items()]).to_csv(
        OUT / "DATA_GATE_SUMMARY.csv", index=False)

    print(f"\n=== DATA GATE: {n_ok} jeux retenus ({report['gate_status']}) ===")
    print(pd.read_csv(OUT / "DATA_GATE_SUMMARY.csv").to_string(index=False))
    print("TEST_OPENED: NO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
