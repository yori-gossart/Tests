"""
PHASE 11D -- cross-sheet consistency analysis of the official EPA workbook.

This analysis is only possible now that the workbook itself is in hand, and it
is diagnostic, not corrective: it does not try to make the reproduction pass.
Its purpose is to establish, from the official data alone, WHAT the workbook
does and does not determine about the Time Horizon experiment.

Two things are recovered:

  1. the nominal sensor density, by triangulating the four sheets that all
     report a zero-perturbation Net3 case;
  2. the fact that the Network Size sheet's Net3 case is NOT the same
     configuration as the Time Horizon sheet's Net3 case, which bounds what
     the workbook can pin down.

One thing is shown to remain under-determined: the definition of "accuracy".
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "phase11_epa" / "phase11d"
XLSX = REPO / "phase11_epa" / "official" / "Data_A-pg4z_TestSourceInversion_Haxton_20160728.xlsx"
N_NET3 = 97


def n_ge_from_specificity(spec: float, n: int = N_NET3) -> float:
    """Invert the exactly-verified specificity definition."""
    return (1.0 - spec / 100.0) * n


def collect_nominal_net3() -> pd.DataFrame:
    """Every zero-perturbation Net3 case the workbook reports, all sheets."""
    rows = []

    me = pd.read_excel(XLSX, sheet_name="Measurement Error", header=None)
    for method, c0 in [("probability_based", 0), ("contaminant_status", 5), ("optimization", 10)]:
        acc, spec = float(me.iat[4, c0 + 2]), float(me.iat[4, c0 + 3])
        rows.append({"sheet": "Measurement Error", "condition": "FPR=0, FNR=0",
                     "method": method, "accuracy": acc, "specificity": spec})

    mo = pd.read_excel(XLSX, sheet_name="Modeling Error", header=None)
    for method, c0 in [("probability_based", 0), ("contaminant_status", 6), ("optimization", 12)]:
        acc, spec = float(mo.iat[4, c0 + 1]), float(mo.iat[4, c0 + 3])
        rows.append({"sheet": "Modeling Error", "condition": "demand error 0%",
                     "method": method, "accuracy": acc, "specificity": spec})

    th = pd.read_excel(XLSX, sheet_name="Time Horizon", header=None)
    for method, c0 in [("probability_based", 0), ("contaminant_status", 4), ("optimization", 8)]:
        for r, h in [(7, 8), (8, 16), (9, 24)]:
            rows.append({"sheet": "Time Horizon", "condition": f"{h}h (plateau)",
                         "method": method, "accuracy": float(th.iat[r, c0 + 1]),
                         "specificity": float(th.iat[r, c0 + 2])})

    ns = pd.read_excel(XLSX, sheet_name="Network Size", header=None)
    for method, c0 in [("probability_based", 0), ("contaminant_status", 5), ("optimization", 10)]:
        rows.append({"sheet": "Network Size", "condition": "Net3",
                     "method": method, "accuracy": 100.0,
                     "specificity": float(ns.iat[4, c0 + 1])})

    df = pd.DataFrame(rows)
    df["n_ge_implied"] = df.specificity.map(n_ge_from_specificity).round(2)
    return df


def sensor_density_bracket() -> pd.DataFrame:
    """Which sensor density reproduces the nominal specificity of each method."""
    sp = pd.read_excel(XLSX, sheet_name="Sensor Placement", header=None)
    rows = []
    for placement, r0 in [("optimal", 5), ("random", 16)]:
        for method, c0 in [("probability_based", 0), ("contaminant_status", 4), ("optimization", 8)]:
            for i in range(5):
                rows.append({"placement": placement, "method": method,
                             "density_pct": float(sp.iat[r0 + i, c0]),
                             "specificity": float(sp.iat[r0 + i, c0 + 1]),
                             "n_sensors_net3": round(float(sp.iat[r0 + i, c0]) / 100 * N_NET3, 1)})
    return pd.DataFrame(rows)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    nom = collect_nominal_net3()
    nom.to_csv(OUT / "CROSSSHEET_NOMINAL_NET3.csv", index=False)
    print("Every zero-perturbation Net3 case in the workbook:\n")
    print(nom.to_string(index=False))

    sd = sensor_density_bracket()
    sd.to_csv(OUT / "CROSSSHEET_SENSOR_DENSITY.csv", index=False)
    print("\n\nSensor Placement sheet, specificity by density:\n")
    print(sd.pivot_table(index=["placement", "density_pct", "n_sensors_net3"],
                         columns="method", values="specificity").to_string())

    findings = {}

    # 1. nominal density, per method, by nearest published specificity
    nominal_spec = (nom[nom.sheet.isin(["Measurement Error", "Modeling Error"])]
                    .groupby("method").specificity.mean())
    bracket = {}
    for method, spec in nominal_spec.items():
        opt = sd[(sd.placement == "optimal") & (sd.method == method)]
        nearest = opt.iloc[(opt.specificity - spec).abs().argmin()]
        bracket[method] = {
            "nominal_specificity": round(float(spec), 2),
            "nearest_density_pct": float(nearest.density_pct),
            "nearest_density_specificity": float(nearest.specificity),
            "implied_n_sensors_net3": float(nearest.n_sensors_net3),
        }
    findings["recovered_nominal_sensor_density"] = bracket

    # 2. Network Size Net3 vs Time Horizon plateau -- same network, same
    #    method, different configuration
    disagreement = {}
    for method in nom.method.unique():
        thp = nom[(nom.sheet == "Time Horizon") & (nom.method == method)].specificity.mean()
        nsz = nom[(nom.sheet == "Network Size") & (nom.method == method)].specificity.iloc[0]
        disagreement[method] = {
            "time_horizon_plateau_specificity": round(float(thp), 2),
            "network_size_net3_specificity": round(float(nsz), 2),
            "gap_points": round(float(thp - nsz), 2),
            "n_ge_time_horizon": round(n_ge_from_specificity(thp), 1),
            "n_ge_network_size": round(n_ge_from_specificity(nsz), 1),
        }
    findings["net3_configuration_disagreement_between_sheets"] = disagreement

    # 3. the accuracy definition, tested against the workbook's own numbers
    th = pd.read_excel(XLSX, sheet_name="Time Horizon", header=None)
    csa_1h_acc, csa_1h_spec = float(th.iat[4, 5]), float(th.iat[4, 6])
    findings["accuracy_definition_remains_underdetermined"] = {
        "csa_1h_accuracy": csa_1h_acc,
        "csa_1h_specificity": csa_1h_spec,
        "csa_1h_n_ge_implied": round(n_ge_from_specificity(csa_1h_spec), 1),
        "csa_network_size_accuracy": 100.0,
        "csa_network_size_n_ge_implied": round(
            n_ge_from_specificity(float(nom[(nom.sheet == "Network Size") &
                                            (nom.method == "contaminant_status")].specificity.iloc[0])), 1),
        "why_underdetermined": (
            "A consistency-based CSA on noise-free observations always retains the true "
            "source, so accuracy would be 100% at every horizon; the workbook reports 20% "
            "at 1h. A noisy CSA that can drop the true source at 1h would drop it more "
            "often at 24h as readings accumulate, yet the workbook reports 100% at 24h. "
            "No set-membership rule over a monotonically growing observation set produces "
            "both. The workbook rules out unique-top-1 (Network Size: accuracy 100% while "
            "30 nodes are as-or-more likely) but does not identify the replacement."),
    }

    (OUT / "CROSSSHEET_FINDINGS.json").write_text(json.dumps(findings, indent=2))
    print("\n\n" + "=" * 72)
    print(json.dumps(findings, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
