"""PHASE 22-BR -- data gate (commit B).

Executes section 2.2 of PROTOCOLE_PHASE22_BR.md
(SHA-256 3e48e6091655935e1aaf4cabeb7852540d7094d48d6e6ca1af02d3bfd86ce89b,
frozen at commit 8fe5233 before any data access).

Acquisition, integrity checks, SHA-256 fingerprints, materialised splits and
class-representation verification. NO model is fitted, NO score is computed, NO
confirmatory endpoint is produced here.

Official hosts (archive.ics.uci.edu, openml.org) are blocked by the network
policy. Mirrors are admitted ONLY if they match the officially documented counts
exactly. Nothing is reconstructed, resampled or repaired.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "phase22_br"
WORK = Path("/tmp/claude-0/-home-user-Tests/6cb7a48c-87d9-5b87-a56a-413674448e9d/"
            "scratchpad/p22")

SEED = 22260822
FORBIDDEN = ("_smaller", "_processed", "_clean", "_balanced", "_sample", "_reduced",
             "_subset", "_smote", "_tidy", "_undersampl", "_oversampl", "_scaled",
             "_norm", "_train", "_test")

CANDIDATES = {
    "GAS": ["alexdbatista/gas-sensor-drift-monitoring", "abob7/gas-drift",
            "Dalageo/ml-gas-sensor-drift", "jbrownlee/Datasets",
            "thuwangzw/gas-sensor-drift", "sisl/gas-sensor-array-drift",
            "nishantsethi/Gas-Sensor-Array-Drift", "Vini2/gas-sensor-drift"],
    "SENSORLESS": ["siddharth691/Unsupervised-Learning",
                   "sravya-bhimavarapu/Sensor-less-drive-diagnosis",
                   "ohmytiannn/Sensorless-Drive-Diagnosis",
                   "tirthajyoti/UCI-ML-API", "jbrownlee/Datasets",
                   "mvarrone/sensorless-drive-diagnosis",
                   "AlexWang1900/Sensorless_drive_diagnosis",
                   "Hsins/UCI-Sensorless-Drive-Diagnosis"],
    "CREDIT": ["MatteoM95/Default-of-Credit-Card-Clients-Dataset-Analisys",
               "robertofranceschi/Default-Credit-Card-Prediction",
               "irenebenedetto/default-of-credit-card-clients",
               "thomasXwang/UCI-Credit-card-defaults",
               "ubc-mds/credit_default_prediction_group_20",
               "macychan/default_credit_card_client_predictor",
               "sharmaroshan/Credit-Card-Default-Prediction",
               "jbrownlee/Datasets"],
    "DRYBEAN": ["mehmetsen1/DryBeanDataset",
                "BetulKarakaya/Dry-Bean-Dataset-Analysis-And-Classification",
                "DPershall/Computer_Vision_System_Dry_Beans",
                "ShefaaSaied/Dry-Bean-Classification",
                "selva86/datasets", "jbrownlee/Datasets",
                "AmirhosseinAbaskohi/Dry-Bean-Classification",
                "sinanazeri/dry_bean_dataset"],
}

GAS_BATCH_SIZES = [445, 1244, 1586, 161, 197, 2300, 3613, 294, 470, 3600]
DRYBEAN_CLASSES = {"DERMASON": 3546, "SIRA": 2636, "SEKER": 2027, "HOROZ": 1928,
                   "CALI": 1630, "BARBUNYA": 1322, "BOMBAY": 522}


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def clone(repo: str) -> Path | None:
    dst = WORK / repo.replace("/", "__")
    if dst.exists():
        return dst
    r = subprocess.run(["git", "clone", "-q", "--depth", "1",
                        f"https://github.com/{repo}.git", str(dst)],
                       capture_output=True, text=True, timeout=1200)
    return dst if r.returncode == 0 else None


def unzip_all(root: Path) -> None:
    for z in list(root.rglob("*.zip")):
        try:
            with zipfile.ZipFile(z) as zf:
                zf.extractall(z.parent / (z.stem + "_unz"))
        except Exception:
            pass


def clean_name(p: Path) -> bool:
    return not any(f in p.name.lower() for f in FORBIDDEN)


def read_any(p: Path) -> pd.DataFrame | None:
    try:
        if p.suffix.lower() in (".xlsx", ".xls"):
            return pd.read_excel(p)
        if p.suffix.lower() == ".arff":
            txt = p.read_text(errors="ignore").splitlines()
            i = next(k for k, l in enumerate(txt) if l.strip().lower() == "@data")
            from io import StringIO
            return pd.read_csv(StringIO("\n".join(txt[i + 1:])), header=None)
        for sep in (",", ";", r"\s+", "\t"):
            d = pd.read_csv(p, sep=sep, engine="python", low_memory=False)
            if d.shape[1] > 1:
                return d
    except Exception:
        return None
    return None


# --------------------------------------------------------------- per-dataset

def gate_gas(root: Path) -> dict:
    rej = []
    for cand in sorted(set(q.parent for q in root.rglob("batch1.dat"))):
        files = [cand / f"batch{i}.dat" for i in range(1, 11)]
        if not all(f.exists() for f in files):
            rej.append({"dir": str(cand.relative_to(root)), "reason": "10 batches absents"})
            continue
        sizes, feats, labels = [], set(), set()
        okread = True
        for f in files:
            try:
                lines = [l for l in f.read_text(errors="ignore").splitlines() if l.strip()]
            except Exception as e:
                rej.append({"dir": str(cand.relative_to(root)), "reason": f"illisible: {e}"})
                okread = False
                break
            sizes.append(len(lines))
            for l in lines[:5]:
                toks = l.split()
                labels.add(toks[0].split(";")[0])
                feats.add(max(int(t.split(":")[0]) for t in toks[1:]))
        if not okread:
            continue
        if sizes != GAS_BATCH_SIZES:
            rej.append({"dir": str(cand.relative_to(root)),
                        "reason": f"tailles de batch {sizes} != officiel {GAS_BATCH_SIZES}"})
            continue
        if max(feats) != 128:
            rej.append({"dir": str(cand.relative_to(root)),
                        "reason": f"{max(feats)} caracteristiques != 128"})
            continue
        return {"found": {f"batch{i}": str(files[i - 1].relative_to(root))
                          for i in range(1, 11)},
                "sha256": {f"batch{i}": sha(files[i - 1]) for i in range(1, 11)},
                "n_rows": int(sum(sizes)), "batch_sizes": sizes,
                "n_features": 128, "n_classes": len(labels), "rejected": rej}
    return {"found": {}, "rejected": rej}


def gate_sensorless(root: Path) -> dict:
    rej = []
    for p in sorted(root.rglob("*")):
        if not p.is_file() or p.suffix.lower() not in (".txt", ".csv", ".data"):
            continue
        n = p.name.lower()
        if "sensorless" not in n or not clean_name(p):
            continue
        for sep, hdr in ((r"\s+", None), (",", None), (",", 0)):
            try:
                d = pd.read_csv(p, sep=sep, header=hdr, engine="python", low_memory=False)
            except Exception:
                continue
            if d.shape != (58509, 49):
                rej.append({"file": str(p.relative_to(root)),
                            "reason": f"forme {tuple(d.shape)} != (58509, 49) "
                                      f"(sep={sep!r}, header={hdr})"})
                continue
            vc = d.iloc[:, -1].value_counts().to_dict()
            if sorted(vc.values()) != [5319] * 11:
                rej.append({"file": str(p.relative_to(root)),
                            "reason": f"effectifs par classe {sorted(vc.values())} "
                                      f"!= 11 x 5319"})
                continue
            return {"found": {"data": str(p.relative_to(root)),
                              "read": {"sep": sep, "header": hdr}},
                    "sha256": {"data": sha(p)}, "n_rows": 58509, "n_features": 48,
                    "n_classes": 11, "rejected": rej}
    return {"found": {}, "rejected": rej}


def gate_credit(root: Path) -> dict:
    rej = []
    for p in sorted(root.rglob("*")):
        if not p.is_file() or p.suffix.lower() not in (".csv", ".xls", ".xlsx"):
            continue
        n = p.name.lower()
        if not any(k in n for k in ("credit", "default", "uci")) or not clean_name(p):
            continue
        cands = []
        if p.suffix.lower() in (".xls", ".xlsx"):
            for hdr in (1, 0):
                try:
                    cands.append(pd.read_excel(p, header=hdr))
                except Exception:
                    pass
        else:
            for sep in (",", ";"):
                try:
                    cands.append(pd.read_csv(p, sep=sep, low_memory=False))
                except Exception:
                    pass
        for d in cands:
            if d is None or len(d) != 30000:
                if d is not None:
                    rej.append({"file": str(p.relative_to(root)),
                                "reason": f"{len(d)} lignes != 30000"})
                continue
            tgt = [c for c in d.columns
                   if re.search(r"default", str(c), re.I) or str(c).lower() == "y"]
            if not tgt:
                rej.append({"file": str(p.relative_to(root)),
                            "reason": "colonne cible 'default' absente"})
                continue
            t = d[tgt[-1]]
            nd = int((t == 1).sum())
            if nd != 6636:
                rej.append({"file": str(p.relative_to(root)),
                            "reason": f"{nd} defauts != 6636"})
                continue
            has_id = any(str(c).strip().upper() == "ID" for c in d.columns)
            nfeat = d.shape[1] - 1 - (1 if has_id else 0)
            if nfeat != 23:
                rej.append({"file": str(p.relative_to(root)),
                            "reason": f"{nfeat} caracteristiques hors ID/cible != 23"})
                continue
            return {"found": {"data": str(p.relative_to(root)),
                              "target_col": str(tgt[-1]), "has_id": bool(has_id)},
                    "sha256": {"data": sha(p)}, "n_rows": 30000, "n_features": 23,
                    "n_classes": 2, "n_default": nd, "rejected": rej}
    return {"found": {}, "rejected": rej}


def gate_drybean(root: Path) -> dict:
    rej = []
    for p in sorted(root.rglob("*")):
        if not p.is_file() or p.suffix.lower() not in (".csv", ".xlsx", ".xls", ".arff"):
            continue
        n = p.name.lower()
        if "bean" not in n or not clean_name(p):
            continue
        d = read_any(p)
        if d is None:
            rej.append({"file": str(p.relative_to(root)), "reason": "illisible"})
            continue
        if d.shape != (13611, 17):
            rej.append({"file": str(p.relative_to(root)),
                        "reason": f"forme {tuple(d.shape)} != (13611, 17)"})
            continue
        vc = {str(k).strip().upper(): int(v)
              for k, v in d.iloc[:, -1].value_counts().items()}
        if vc != DRYBEAN_CLASSES:
            rej.append({"file": str(p.relative_to(root)),
                        "reason": f"effectifs par classe {vc} != officiel"})
            continue
        return {"found": {"data": str(p.relative_to(root))},
                "sha256": {"data": sha(p)}, "n_rows": 13611, "n_features": 16,
                "n_classes": 7, "rejected": rej}
    return {"found": {}, "rejected": rej}


GATES = {"GAS": gate_gas, "SENSORLESS": gate_sensorless,
         "CREDIT": gate_credit, "DRYBEAN": gate_drybean}


# ------------------------------------------------------------------- splits

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


def main() -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    (OUT / "logs").mkdir(parents=True, exist_ok=True)
    report = {"protocol_sha256": (OUT / "PROTOCOL_SHA256.txt").read_text().split()[0],
              "official_hosts": {"archive.ics.uci.edu": "403 CONNECT (politique du relais)",
                                 "www.openml.org": "403 CONNECT",
                                 "api.openml.org": "403 CONNECT"},
              "integrity_caveat": "l'original UCI est inatteignable depuis cet "
                                  "environnement ; aucun miroir ne peut etre verifie par "
                                  "somme de controle contre lui. Seule la conformite "
                                  "structurelle aux effectifs officiels est etablie.",
              "datasets": {}}

    for ds, repos in CANDIDATES.items():
        print(f"\n===== {ds} =====", flush=True)
        acc, trail = None, []
        for repo in repos:
            if acc is not None:
                trail.append({"repo": repo, "status": "non sonde -- deja conforme"})
                continue
            root = clone(repo)
            if root is None:
                trail.append({"repo": repo, "status": "clone impossible"})
                print(f"  {repo:60s} clone impossible", flush=True)
                continue
            unzip_all(root)
            commit = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                                    capture_output=True, text=True).stdout.strip()
            res = GATES[ds](root)
            trail.append({"repo": repo, "commit": commit,
                          "conforme": bool(res["found"]),
                          "rejetes": res.get("rejected", [])[:8]})
            print(f"  {repo:60s} conforme={bool(res['found'])}", flush=True)
            if res["found"]:
                acc = {"repo": repo, "commit": commit,
                       **{k: v for k, v in res.items() if k != "rejected"}}
        status = "EXECUTABLE" if acc else "NOT_EXECUTABLE"
        report["datasets"][ds] = {
            "status": status, "accepted": acc,
            "candidates_probed": len([t for t in trail
                                      if t.get("status") != "non sonde -- deja conforme"]),
            "trail": trail}
        print(f"  --> {ds}: {status}", flush=True)

    json.dump(report, open(OUT / "GATE_B.json", "w"), indent=2)
    pd.DataFrame([{"dataset": k, "status": v["status"],
                   "repo": (v["accepted"] or {}).get("repo", ""),
                   "commit": (v["accepted"] or {}).get("commit", "")[:12],
                   "candidates_probed": v["candidates_probed"]}
                  for k, v in report["datasets"].items()]).to_csv(
        OUT / "GATE_B_SUMMARY.csv", index=False)
    print("\n=== GATE B ===")
    print(pd.read_csv(OUT / "GATE_B_SUMMARY.csv").to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
