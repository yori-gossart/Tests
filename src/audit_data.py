"""
Audit every file under data/raw/ and emit DATA_MANIFEST.json.

For each raw artefact we record: SHA256, byte size, row count, column count,
column names, temporal coverage and missing-value counts, using a parser
appropriate to the file type (EPANET .inp, BattLeDIM .yalm, .xlsx, .csv, .m).

Raw files are opened read-only and are never rewritten.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yaml

REPO = Path(__file__).resolve().parents[1]
RAW = REPO / "data" / "raw"
OUT = REPO / "DATA_MANIFEST.json"

CHUNK = 1 << 20


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def count_lines(path: Path) -> int:
    n = 0
    with path.open("rb") as fh:
        for _ in fh:
            n += 1
    return n


def audit_inp(path: Path) -> dict:
    """Summarise an EPANET input file: sections, element counts, pattern span."""
    sections: dict[str, int] = {}
    current = None
    with path.open("r", encoding="latin-1") as fh:
        for line in fh:
            s = line.strip()
            if not s or s.startswith(";"):
                continue
            m = re.match(r"^\[(\w+)\]", s)
            if m:
                current = m.group(1).upper()
                sections.setdefault(current, 0)
                continue
            if current:
                sections[current] += 1

    info: dict = {
        "parser": "epanet_inp",
        "sections": sections,
        "n_lines": count_lines(path),
    }

    # Hydraulic detail via wntr (authoritative element counts + pattern span).
    try:
        import wntr

        wn = wntr.network.WaterNetworkModel(str(path))
        pat_lens = {p: len(wn.get_pattern(p).multipliers) for p in wn.pattern_name_list}
        hist: dict[str, int] = {}
        for v in pat_lens.values():
            hist[str(v)] = hist.get(str(v), 0) + 1
        ts = int(wn.options.time.pattern_timestep or 0)
        max_len = max(pat_lens.values()) if pat_lens else 0
        info["network"] = {
            "n_nodes": wn.num_nodes,
            "n_junctions": wn.num_junctions,
            "n_tanks": wn.num_tanks,
            "n_reservoirs": wn.num_reservoirs,
            "n_links": wn.num_links,
            "n_pipes": wn.num_pipes,
            "n_pumps": wn.num_pumps,
            "n_valves": wn.num_valves,
            "n_patterns": len(wn.pattern_name_list),
            "pattern_timestep_s": ts,
            "pattern_length_histogram": hist,
            "max_pattern_span_days": round(max_len * ts / 86400.0, 4) if ts else None,
            "hydraulic_timestep_s": int(wn.options.time.hydraulic_timestep or 0),
            "demand_model": str(wn.options.hydraulic.demand_model),
        }
        info["n_rows"] = wn.num_nodes
        info["n_cols"] = None
        info["columns"] = None
    except Exception as exc:  # pragma: no cover - reported, never silently dropped
        info["network_parse_error"] = f"{type(exc).__name__}: {exc}"

    return info


def audit_yalm(path: Path) -> dict:
    """BattLeDIM .yalm: configuration + leak table (leak rows are CSV-in-YAML)."""
    text = path.read_text(encoding="latin-1")
    info: dict = {"parser": "battledim_yalm", "n_lines": count_lines(path)}
    try:
        doc = yaml.safe_load(text)
    except Exception as exc:
        info["yaml_parse_error"] = f"{type(exc).__name__}: {exc}"
        return info

    if not isinstance(doc, dict):
        info["note"] = "top level is not a mapping"
        return info

    info["keys"] = sorted(doc.keys())
    for key in ("pressure_sensors", "flow_sensors", "level_sensors", "amrs"):
        if key in doc and doc[key] is not None:
            info[f"n_{key}"] = len(doc[key])
            info[key] = [str(x) for x in doc[key]]
    if "times" in doc:
        info["period"] = {k: str(v) for k, v in doc["times"].items()}
    if "Network" in doc:
        info["network_file"] = doc["Network"].get("filename")

    leaks = doc.get("leakages")
    if leaks:
        rows = [str(r) for r in leaks if not str(r).lstrip().startswith("#")]
        parsed = []
        for r in rows:
            parts = [p.strip() for p in r.split(",")]
            if len(parts) >= 6:
                parsed.append(parts[:6])
        cols = ["linkID", "startTime", "endTime", "leakDiameter_m", "leakType", "peakTime"]
        df = pd.DataFrame(parsed, columns=cols)
        info["n_rows"] = len(df)
        info["n_cols"] = len(cols)
        info["columns"] = cols
        info["missing_values_total"] = int(df.isna().sum().sum())
        if len(df):
            info["leak_period"] = {
                "first_start": df["startTime"].min(),
                "last_end": df["endTime"].max(),
            }
            info["leak_type_counts"] = df["leakType"].value_counts().to_dict()
            info["leak_link_ids"] = df["linkID"].tolist()
    return info


def audit_leak_table(path: Path) -> dict:
    """Bare leak-table file (one CSV row per leak, '#'-prefixed header)."""
    return audit_yalm(path)


def audit_xlsx(path: Path) -> dict:
    info: dict = {"parser": "xlsx", "sheets": {}}
    try:
        book = pd.read_excel(path, sheet_name=None)
    except Exception as exc:
        info["parse_error"] = f"{type(exc).__name__}: {exc}"
        return info
    total_rows = 0
    for name, df in book.items():
        entry = {
            "n_rows": int(len(df)),
            "n_cols": int(df.shape[1]),
            "columns": [str(c) for c in df.columns],
            "missing_values_total": int(df.isna().sum().sum()),
        }
        for cand in ("Timestamp", "time_stamp"):
            if cand in df.columns and len(df):
                entry["period"] = {"start": str(df[cand].iloc[0]), "end": str(df[cand].iloc[-1])}
                break
        info["sheets"][name] = entry
        total_rows += len(df)
    info["n_rows"] = total_rows
    info["n_cols"] = None
    return info


def audit_csv(path: Path) -> dict:
    info: dict = {"parser": "csv"}
    try:
        df = pd.read_csv(path)
    except Exception as exc:
        info["parse_error"] = f"{type(exc).__name__}: {exc}"
        return info
    info["n_rows"] = int(len(df))
    info["n_cols"] = int(df.shape[1])
    info["columns"] = [str(c) for c in df.columns]
    info["missing_values_total"] = int(df.isna().sum().sum())
    info["missing_values_per_column"] = {
        str(c): int(v) for c, v in df.isna().sum().items() if v
    }
    first = df.columns[0]
    if len(df) and re.search(r"time|stamp|date", str(first), re.I):
        info["period"] = {"start": str(df[first].iloc[0]), "end": str(df[first].iloc[-1])}
    return info


def audit_text(path: Path) -> dict:
    return {"parser": "text", "n_lines": count_lines(path)}


def audit_file(path: Path) -> dict:
    suffix = path.suffix.lower()
    stat = path.stat()
    entry: dict = {
        "path": str(path.relative_to(REPO)),
        "sha256": sha256_of(path),
        "size_bytes": stat.st_size,
    }
    try:
        if suffix == ".inp":
            entry.update(audit_inp(path))
        elif suffix == ".yalm":
            entry.update(audit_yalm(path))
        elif suffix == ".xlsx":
            entry.update(audit_xlsx(path))
        elif suffix == ".csv":
            entry.update(audit_csv(path))
        else:
            entry.update(audit_text(path))
    except Exception as exc:  # keep the manifest complete even on parse failure
        entry["audit_error"] = f"{type(exc).__name__}: {exc}"
    return entry


def main() -> int:
    if not RAW.exists():
        print(f"missing {RAW}", file=sys.stderr)
        return 1

    files = sorted(p for p in RAW.rglob("*") if p.is_file())
    entries = [audit_file(p) for p in files]

    manifest = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "repo_relative_root": "data/raw",
        "n_files": len(entries),
        "total_bytes": sum(e["size_bytes"] for e in entries),
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "pandas": pd.__version__,
        },
        "provenance": json.loads((RAW / "PROVENANCE.json").read_text())
        if (RAW / "PROVENANCE.json").exists()
        else None,
        "files": entries,
    }

    try:
        import wntr

        manifest["environment"]["wntr"] = wntr.__version__
    except Exception:
        pass

    OUT.write_text(json.dumps(manifest, indent=2, sort_keys=False) + "\n")
    digest = hashlib.sha256(OUT.read_bytes()).hexdigest()
    print(f"wrote {OUT} ({len(entries)} files, {manifest['total_bytes']} bytes)")
    print(f"DATA_MANIFEST.json sha256 = {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
