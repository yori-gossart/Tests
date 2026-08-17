"""PHASE 21-IR -- acquisition and Gate A (structural conformance).

Executes section 2 of PROTOCOLE_PHASE21_IR.md. No model is fitted here, no
endpoint is computed. The only outputs are: which datasets are EXECUTABLE and
which are NOT_EXECUTABLE, with the exact reason.

Official hosts are blocked by the network policy (403 at CONNECT, logged in
logs/host_probe.log). Mirrors are therefore searched, bounded to 6 candidate
repositories per dataset, and admitted ONLY if they match the officially
documented counts exactly. Nothing is reconstructed, resampled or repaired.
"""

from __future__ import annotations

import json
import subprocess
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "phase21_ir"
WORK = Path("/tmp/claude-0/-home-user-Tests/6cb7a48c-87d9-5b87-a56a-413674448e9d/"
            "scratchpad/p21")
DATA = WORK / "gateA"

FORBIDDEN = ("_smaller", "_processed", "_clean", "_balanced", "_sample", "_tidy",
             "_reduced", "_subset", "_undersampl", "_oversampl", "_smote")

CANDIDATES = {
    "APS": ["nipunmanral/Classification-APS-Failure-at-Scania-Trucks",
            "Sunita778/Scania-Truck-Failures-Detection",
            "Nisarg9795/Anomaly-Detection-APS-failures-in-Scania-trucks",
            "tianxiny/APS-Failure-at-Scania-Trucks",
            "mrunal46/APS-Failure-at-Scania-Trucks",
            "chaitra31595/Machine-Learning---APS-Failure-at-Scania-Trucks-Data-Set"],
    "SECOM": ["hnrosa/uci-secom-fault-detection",
              "Meena-Mani/SECOM_class_imbalance",
              "klimburg/SECOM_Analysis",
              "sharmaroshan/SECOM-Detecting-Defected-Items",
              "Eason0227/Semiconductor-Manufacturing-Procees-Prediction",
              "alalehrz/SECOM_classification"],
    "STEEL": ["Sanikommus/Steel_Plates_Faults_Dataset",
              "tmbuthia/Steel-Plates-Faults-Prediction-Using-Neural-Networks",
              "orestasdulinskas/steel_plate_defect_prediction",
              "mrchandrayee/Steel-Plate-Defect-Prediction",
              "ricardoevvargas/awesome-industry40-datasets",
              "makinarocks/awesome-industrial-machine-datasets"],
    "HAR": ["KLEdlerILSTU/UCI-HAR-Dataset",
            "ahmedtadde/UCI-HAR-Dataset",
            "Cheukting/UCI_HAR_Dataset",
            "martiniblack/UCI-HAR",
            "sudar/UCI-HAR-Dataset-Analysis",
            "connorcl/processed-uci-har-dataset"],
}

OFFICIAL = {
    "APS": {"train_shape": (60000, 171), "train_classes": {"neg": 59000, "pos": 1000},
            "test_shape": (16000, 171), "test_classes": {"neg": 15625, "pos": 375}},
    "SECOM": {"data_shape": (1567, 590), "labels_rows": 1567,
              "classes": {-1: 1463, 1: 104}},
    "STEEL": {"shape": (1941, 34)},
    "HAR": {"X_train": (7352, 561), "X_test": (2947, 561),
            "n_activities": 6, "subjects_train": 21, "subjects_test": 9},
}


def clone(repo: str) -> Path | None:
    dst = WORK / repo.split("/")[-1]
    if dst.exists():
        return dst
    r = subprocess.run(["git", "clone", "-q", "--depth", "1",
                        f"https://github.com/{repo}.git", str(dst)],
                       capture_output=True, text=True, timeout=900)
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


# ------------------------------------------------------------------ gates

def gate_aps(root: Path) -> dict:
    o = OFFICIAL["APS"]
    found = {"train": None, "test": None}
    rejected = []
    for p in sorted(root.rglob("*.csv")):
        if "aps" not in p.name.lower():
            continue
        if not clean_name(p):
            rejected.append({"file": str(p.relative_to(root)),
                             "reason": "nom signalant une transformation"})
            continue
        try:
            d = pd.read_csv(p, low_memory=False)
        except Exception as e:
            rejected.append({"file": str(p.relative_to(root)), "reason": f"illisible: {e}"})
            continue
        if "class" not in d.columns:
            rejected.append({"file": str(p.relative_to(root)),
                             "reason": "colonne 'class' absente"})
            continue
        vc = d["class"].value_counts().to_dict()
        shp = tuple(d.shape)
        for k in ("train", "test"):
            if shp == o[f"{k}_shape"] and vc == o[f"{k}_classes"]:
                found[k] = str(p.relative_to(root))
        if shp not in (o["train_shape"], o["test_shape"]):
            rejected.append({"file": str(p.relative_to(root)),
                             "reason": f"forme {shp} != officiel "
                                       f"{o['train_shape']} ou {o['test_shape']}"})
    return {"found": found, "rejected": rejected}


def gate_secom(root: Path) -> dict:
    o = OFFICIAL["SECOM"]
    found = {"data": None, "labels": None}
    rejected = []
    for p in sorted(root.rglob("*")):
        if not p.is_file() or p.suffix.lower() not in (".data", ".txt", ".csv"):
            continue
        n = p.name.lower()
        if "secom" not in n or not clean_name(p):
            continue
        try:
            if "label" in n:
                d = pd.read_csv(p, sep=r"\s+", header=None, engine="python")
                if len(d) == o["labels_rows"]:
                    found["labels"] = str(p.relative_to(root))
                else:
                    rejected.append({"file": str(p.relative_to(root)),
                                     "reason": f"{len(d)} lignes != {o['labels_rows']}"})
            else:
                d = pd.read_csv(p, sep=r"\s+", header=None, engine="python",
                                na_values=["NaN"])
                if tuple(d.shape) == o["data_shape"]:
                    found["data"] = str(p.relative_to(root))
                else:
                    rejected.append({"file": str(p.relative_to(root)),
                                     "reason": f"forme {tuple(d.shape)} != "
                                               f"{o['data_shape']}"})
        except Exception as e:
            rejected.append({"file": str(p.relative_to(root)), "reason": f"illisible: {e}"})
    return {"found": found, "rejected": rejected}


def gate_steel(root: Path) -> dict:
    o = OFFICIAL["STEEL"]
    found = {"data": None}
    rejected = []
    for p in sorted(root.rglob("*")):
        if not p.is_file() or p.suffix.lower() not in (".nna", ".txt", ".csv", ".data"):
            continue
        n = p.name.lower()
        if not any(k in n for k in ("fault", "steel")) or not clean_name(p):
            continue
        for sep, hdr in ((r"\s+", None), (",", 0), (",", None)):
            try:
                d = pd.read_csv(p, sep=sep, header=hdr, engine="python")
            except Exception:
                continue
            if tuple(d.shape) == o["shape"]:
                found["data"] = str(p.relative_to(root))
                found["read"] = {"sep": sep, "header": hdr}
                return {"found": found, "rejected": rejected}
            rejected.append({"file": str(p.relative_to(root)),
                             "reason": f"forme {tuple(d.shape)} != {o['shape']} "
                                       f"(sep={sep!r}, header={hdr})"})
    return {"found": found, "rejected": rejected}


def gate_har(root: Path) -> dict:
    o = OFFICIAL["HAR"]
    rejected = []
    for cand in sorted(root.rglob("X_train.txt")):
        base = cand.parent.parent
        need = {"X_train": base / "train" / "X_train.txt",
                "y_train": base / "train" / "y_train.txt",
                "s_train": base / "train" / "subject_train.txt",
                "X_test": base / "test" / "X_test.txt",
                "y_test": base / "test" / "y_test.txt",
                "s_test": base / "test" / "subject_test.txt"}
        if not all(v.exists() for v in need.values()):
            rejected.append({"dir": str(base.relative_to(root)),
                             "reason": "fichiers officiels incomplets"})
            continue
        try:
            Xtr = np.loadtxt(need["X_train"])
            Xte = np.loadtxt(need["X_test"])
            ytr = np.loadtxt(need["y_train"], dtype=int)
            yte = np.loadtxt(need["y_test"], dtype=int)
            str_ = np.loadtxt(need["s_train"], dtype=int)
            ste = np.loadtxt(need["s_test"], dtype=int)
        except Exception as e:
            rejected.append({"dir": str(base.relative_to(root)), "reason": f"illisible: {e}"})
            continue
        ok = (Xtr.shape == o["X_train"] and Xte.shape == o["X_test"]
              and len(ytr) == o["X_train"][0] and len(yte) == o["X_test"][0]
              and len(np.unique(np.r_[ytr, yte])) == o["n_activities"]
              and len(np.unique(str_)) == o["subjects_train"]
              and len(np.unique(ste)) == o["subjects_test"]
              and not set(np.unique(str_)) & set(np.unique(ste)))
        if ok:
            return {"found": {k: str(v.relative_to(root)) for k, v in need.items()},
                    "rejected": rejected}
        rejected.append({"dir": str(base.relative_to(root)),
                         "reason": f"Xtr{Xtr.shape} Xte{Xte.shape} "
                                   f"sujets {len(np.unique(str_))}/{len(np.unique(ste))} "
                                   f"activites {len(np.unique(np.r_[ytr, yte]))}"})
    return {"found": {}, "rejected": rejected}


GATES = {"APS": gate_aps, "SECOM": gate_secom, "STEEL": gate_steel, "HAR": gate_har}
NEEDED = {"APS": ["train", "test"], "SECOM": ["data", "labels"],
          "STEEL": ["data"], "HAR": ["X_train", "y_train", "s_train",
                                     "X_test", "y_test", "s_test"]}


def main() -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    DATA.mkdir(parents=True, exist_ok=True)
    (OUT / "logs").mkdir(parents=True, exist_ok=True)
    report = {}
    for ds, repos in CANDIDATES.items():
        print(f"\n===== {ds} =====", flush=True)
        acc: dict = {}
        trail = []
        for repo in repos:
            if all(k in acc for k in NEEDED[ds]):
                trail.append({"repo": repo, "status": "non sonde -- deja complet"})
                continue
            root = clone(repo)
            if root is None:
                trail.append({"repo": repo, "status": "clone impossible"})
                print(f"  {repo:65s} clone impossible", flush=True)
                continue
            unzip_all(root)
            sha = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                                 capture_output=True, text=True).stdout.strip()
            res = GATES[ds](root)
            got = [k for k, v in res["found"].items() if v and k in NEEDED[ds]]
            for k in got:
                if k not in acc:
                    acc[k] = {"repo": repo, "commit": sha, "path": res["found"][k]}
            trail.append({"repo": repo, "commit": sha, "conformes": got,
                          "rejetes": res["rejected"][:6]})
            print(f"  {repo:65s} conformes={got}", flush=True)
        missing = [k for k in NEEDED[ds] if k not in acc]
        status = "EXECUTABLE" if not missing else "NOT_EXECUTABLE"
        report[ds] = {"status": status, "missing": missing, "accepted": acc,
                      "candidates_probed": len(
                          [t for t in trail if t.get("status") != "non sonde -- deja complet"]),
                      "trail": trail,
                      "integrity_caveat": "l'original UCI est inatteignable depuis cet "
                                          "environnement (403 au CONNECT) ; le miroir ne peut "
                                          "donc pas etre verifie par somme de controle contre "
                                          "lui. Seule la conformite structurelle aux effectifs "
                                          "officiels est verifiee."}
        print(f"  --> {ds}: {status}" + (f" (manquant: {missing})" if missing else ""),
              flush=True)

    (OUT / "GATE_A.json").write_text(json.dumps(report, indent=2))
    rows = [{"dataset": k, "status": v["status"], "missing": ",".join(v["missing"]),
             "candidates_probed": v["candidates_probed"]} for k, v in report.items()]
    pd.DataFrame(rows).to_csv(OUT / "GATE_A_SUMMARY.csv", index=False)
    print("\n=== GATE A ===")
    print(pd.DataFrame(rows).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
