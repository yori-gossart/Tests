"""
Metrics and the official BattLeDIM economic score.

scoring_battledim() is a line-by-line Python port of the organisers' MATLAB
Scoring_Algorithm.m + functions/scoring_function.m (SHA256 in DATA_MANIFEST.json),
using their published parameters:

    xmax      = 300 m      maximum scoring distance for a leak
    costWater = 0.80 EUR   per cubic metre
    costCrew  = 500 EUR    maximum repair-crew cost per assignment

Per detection i against leak j:

    x = 0 if same pipe, else
        min over the four endpoint pairs of the shortest-path node distance
        + half the length of each pipe
    score = water_saved * costWater - (x / xmax) * costCrew   if the detection
            falls inside [t0, tend] and x <= xmax
          = -costCrew                                          otherwise

with water_saved = sum(leak_flow[td:end]) / 12 (5-minute samples of m^3/h).
Aggregation follows the MATLAB loop exactly: detections in time order, a leak
counts once, a repeat detection of an already-found leak scores 0 rather than
counting as a false positive, and a detection matching no leak is a false
positive costing costCrew.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]

XMAX = 300.0
COST_WATER = 0.80
COST_CREW = 500.0


# ---------------------------------------------------------------------------
# Network geometry
# ---------------------------------------------------------------------------


@dataclass
class Topology:
    node_index: dict[str, int]
    link_nodes: dict[str, tuple[str, str]]
    link_length: dict[str, float]
    dist: np.ndarray            # all-pairs shortest path between nodes, metres
    junction_names: list[str]

    @classmethod
    def build(cls, inp_path: Path) -> "Topology":
        import networkx as nx
        import wntr

        wn = wntr.network.WaterNetworkModel(str(inp_path))
        G = nx.Graph()
        link_nodes, link_length = {}, {}
        for name, link in wn.links():
            a, b = link.start_node_name, link.end_node_name
            length = float(getattr(link, "length", 0.0) or 0.0)
            link_nodes[name] = (a, b)
            link_length[name] = length
            w = length if length > 0 else 1.0
            if G.has_edge(a, b):
                G[a][b]["weight"] = min(G[a][b]["weight"], w)
            else:
                G.add_edge(a, b, weight=w)

        nodes = list(G.nodes())
        idx = {n: i for i, n in enumerate(nodes)}
        D = np.full((len(nodes), len(nodes)), np.inf)
        for src, lengths in nx.all_pairs_dijkstra_path_length(G, weight="weight"):
            i = idx[src]
            for dst, d in lengths.items():
                D[i, idx[dst]] = d
        return cls(
            node_index=idx,
            link_nodes=link_nodes,
            link_length=link_length,
            dist=D,
            junction_names=list(wn.junction_name_list),
        )

    def pipe_distance(self, link_a: str, link_b: str) -> float:
        """Official inter-pipe distance: min endpoint distance + half lengths."""
        if link_a == link_b:
            return 0.0
        a1, a2 = self.link_nodes[link_a]
        b1, b2 = self.link_nodes[link_b]
        i1, i2 = self.node_index[a1], self.node_index[a2]
        j1, j2 = self.node_index[b1], self.node_index[b2]
        m = min(
            self.dist[i1, j1], self.dist[i1, j2],
            self.dist[i2, j1], self.dist[i2, j2],
        )
        return float(m + self.link_length[link_a] / 2 + self.link_length[link_b] / 2)

    def node_to_pipe_distance(self, node: str, link: str) -> float:
        a, b = self.link_nodes[link]
        i = self.node_index[node]
        return float(
            min(self.dist[i, self.node_index[a]], self.dist[i, self.node_index[b]])
            + self.link_length[link] / 2
        )


def pipe_level_signatures(
    delta: np.ndarray, scenarios: np.ndarray, topo: Topology
) -> tuple[np.ndarray, list[str]]:
    """Turn the junction-level library into pipe-level signatures.

    A leak on a pipe sits between its two endpoints, so its signature is taken
    as the mean of the endpoint junction signatures. Pipes whose endpoints are
    absent from the library (tank/reservoir links) are dropped.
    """
    pos = {str(s): i for i, s in enumerate(scenarios)}
    sig_nodes = delta.mean(axis=2)  # (n_scen, n_sensors)
    rows, names = [], []
    for link, (a, b) in topo.link_nodes.items():
        ia, ib = pos.get(a), pos.get(b)
        if ia is None and ib is None:
            continue
        if ia is None or ib is None:
            rows.append(sig_nodes[ia if ia is not None else ib])
        else:
            rows.append(0.5 * (sig_nodes[ia] + sig_nodes[ib]))
        names.append(link)
    return np.asarray(rows).T, names  # (n_sensors, n_pipes)


# ---------------------------------------------------------------------------
# Ground truth
# ---------------------------------------------------------------------------


@dataclass
class LeakEvent:
    link_id: str
    start_idx: int
    end_idx: int
    leak_type: str
    diameter_m: float
    flow_cmh: np.ndarray  # per 5-min step over the year, m^3/h


def load_ground_truth(config_path: Path, timestamps: pd.DatetimeIndex,
                      leaks_csv: Path) -> list[LeakEvent]:
    import yaml

    cfg = yaml.safe_load(config_path.read_text(encoding="latin-1"))
    flows = pd.read_csv(leaks_csv, parse_dates=["Timestamp"])
    lookup = {c: flows[c].to_numpy(dtype=np.float64) for c in flows.columns if c != "Timestamp"}
    pos = {t: i for i, t in enumerate(timestamps)}

    events = []
    for raw in cfg["leakages"][1:]:
        parts = [p.strip() for p in str(raw).split(",")]
        if len(parts) < 6:
            continue
        link, st, et, diam, ltype, _peak = parts[:6]
        si = pos.get(pd.Timestamp(st))
        ei = pos.get(pd.Timestamp(et))
        if si is None or ei is None:
            continue
        events.append(
            LeakEvent(
                link_id=link,
                start_idx=si,
                end_idx=ei,
                leak_type=ltype,
                diameter_m=float(diam),
                flow_cmh=lookup.get(link, np.zeros(len(timestamps))),
            )
        )
    return events


# ---------------------------------------------------------------------------
# Official scoring
# ---------------------------------------------------------------------------


def scoring_battledim(detections: list[dict], leaks: list[LeakEvent],
                      topo: Topology) -> dict:
    """Port of Scoring_Algorithm.m. `detections` need 'index' and 'predicted_pipe'."""
    dets = sorted(detections, key=lambda d: d["index"])
    detected: list[int] = []
    per_det_score = []
    delays, matched_pipes = [], []
    FP = 0

    for det in dets:
        td = int(det["index"])
        pipe = det["predicted_pipe"]
        suc, sc, xs = [], [], []
        for j, leak in enumerate(leaks):
            x = topo.pipe_distance(leak.link_id, pipe)
            xs.append(x)
            if leak.start_idx <= td <= leak.end_idx and abs(x) <= XMAX:
                water = float(np.sum(leak.flow_cmh[max(td, 1) : leak.end_idx + 1])) / 12.0
                sc.append(water * COST_WATER - (x / XMAX) * COST_CREW)
                suc.append(j)
            else:
                sc.append(-COST_CREW)

        fresh = [j for j in suc if j not in detected]
        if suc and not fresh:
            per_det_score.append(0.0)          # repeated detection: ignored
        elif fresh:
            j = min(fresh, key=lambda jj: xs[jj])
            per_det_score.append(sc[j])
            detected.append(j)
            delays.append(td - leaks[j].start_idx)
            matched_pipes.append((leaks[j].link_id, pipe, xs[j]))
        else:
            FP += 1
            per_det_score.append(-COST_CREW)

    TP = len(detected)
    FN = len(leaks) - TP
    return {
        "total_score_eur": round(float(np.sum(per_det_score)), 2),
        "TP": TP,
        "FP": FP,
        "FN": FN,
        "n_detections": len(dets),
        "detected_leak_indices": detected,
        "delays_steps": delays,
        "matched": matched_pipes,
    }


# ---------------------------------------------------------------------------
# Standard metrics
# ---------------------------------------------------------------------------


def standard_metrics(score: dict, leaks: list[LeakEvent], topo: Topology,
                     step_minutes: int = 5) -> dict:
    TP, FP, FN = score["TP"], score["FP"], score["FN"]
    recall = TP / len(leaks) if leaks else float("nan")
    precision = TP / (TP + FP) if (TP + FP) else float("nan")
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    delays_h = np.array(score["delays_steps"], dtype=float) * step_minutes / 60.0
    dists = np.array([m[2] for m in score["matched"]], dtype=float)

    per_leak = {}
    for j, leak in enumerate(leaks):
        per_leak[leak.link_id] = 1 if j in score["detected_leak_indices"] else 0

    return {
        "false_forgetting_rate": 1.0 - recall,   # empirical analogue of B
        "recall": recall,
        "precision": precision,
        "f1": f1,
        "false_positives": FP,
        "true_positives": TP,
        "false_negatives": FN,
        "detection_delay_mean_h": float(np.mean(delays_h)) if len(delays_h) else float("nan"),
        "detection_delay_median_h": float(np.median(delays_h)) if len(delays_h) else float("nan"),
        "localisation_distance_mean_m": float(np.mean(dists)) if len(dists) else float("nan"),
        "localisation_distance_median_m": float(np.median(dists)) if len(dists) else float("nan"),
        "battledim_score_eur": score["total_score_eur"],
        "per_leak_detected": per_leak,
        "worst_per_leak_recall": float(min(per_leak.values())) if per_leak else float("nan"),
    }
