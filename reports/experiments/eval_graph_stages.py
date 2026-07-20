#!/usr/bin/env python3
"""Evaluate G / G+L1 stages for the five historical qrels against a fixed bundle.

Companion to ``run_cross_version.py``: that runner bootstraps a fresh bundle in a
temp dir, so it cannot measure a bundle that was mutated in place (e.g. after
``mneme graph ingest`` of agent-extracted entities). This script points at an
existing bundle and reports per-query ranks for the graph-based stages only.

Usage:
    python reports/experiments/eval_graph_stages.py --bundle /path/to/wiki
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "skills" / "mneme" / "scripts"))

from mneme import graphlib, indexlib  # noqa: E402

QRELS = (
    ("H01", "gstack", "AKMedL4gzoLwNwxg1cyc9bdxnPI"),
    ("H02", "Claude Code 工作流", "AKMedL4gzoLwNwxg1cyc9bdxnPI"),
    ("H03", "银行回单", "UCvpdz5z8oZqXTxCpD2cLAObnse"),
    ("H04", "录音", "Sic7dPX3aoxVByxxWqqcZAQunRb"),
    ("H05", "Hermes", "XVFudUEQeoXQjixSS9zckeNonAg"),
)
TOP_K = 10
GRAPH_DEPTH = 2
HYBRID_ALPHA = 0.4
HYBRID_BETA = 0.4
HYBRID_GAMMA = 0.2


def rank_of(paths: list[str], expected: str) -> int | None:
    return next((rank for rank, path in enumerate(paths, start=1) if path == expected), None)


def ndcg(ranks: list[int | None]) -> float:
    return statistics.mean(0.0 if r is None else 1 / math.log2(r + 1) for r in ranks)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    args = parser.parse_args()
    bundle = args.bundle.resolve()
    graph_db = graphlib.graph_index_path(bundle)

    rows = []
    for query_id, query, slug in QRELS:
        expected = f"concepts/{slug}.md"
        graph_out = graphlib.search_graph(graph_db, query, k=TOP_K, depth=GRAPH_DEPTH)
        g_paths = [item["path"] for item in graph_out["candidates"]]
        hybrid_out = indexlib.search_hybrid(
            bundle, query, k=TOP_K,
            alpha=HYBRID_ALPHA, beta=HYBRID_BETA, gamma=HYBRID_GAMMA,
            depth=GRAPH_DEPTH,
        )
        h_paths = [item["path"] for item in hybrid_out["candidates"]]
        rows.append({
            "query_id": query_id,
            "query": query,
            "expected_path": expected,
            "G_rank": rank_of(g_paths, expected),
            "G_candidates": g_paths,
            "G+L1_rank": rank_of(h_paths, expected),
            "G+L1_candidates": h_paths,
        })

    g_ranks = [row["G_rank"] for row in rows]
    h_ranks = [row["G+L1_rank"] for row in rows]
    summary = {
        "G": {
            "Recall@1": sum(r == 1 for r in g_ranks) / len(g_ranks),
            "Recall@10": sum(r is not None for r in g_ranks) / len(g_ranks),
            "MRR@10": statistics.mean(0.0 if r is None else 1 / r for r in g_ranks),
            "nDCG@10": ndcg(g_ranks),
        },
        "G+L1": {
            "Recall@1": sum(r == 1 for r in h_ranks) / len(h_ranks),
            "Recall@10": sum(r is not None for r in h_ranks) / len(h_ranks),
            "MRR@10": statistics.mean(0.0 if r is None else 1 / r for r in h_ranks),
            "nDCG@10": ndcg(h_ranks),
        },
    }
    print(json.dumps({"bundle": str(bundle), "rows": rows, "summary": summary},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
