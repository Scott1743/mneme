from __future__ import annotations

import importlib.util
import math
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "reports" / "experiments" / "run_graph_enrichment_benchmark.py"
SPEC = importlib.util.spec_from_file_location("graph_benchmark", SCRIPT)
assert SPEC and SPEC.loader
benchmark = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(benchmark)


def test_ranked_metrics_single_relevant_document():
    metrics = benchmark.ranked_metrics(["other.md", "target.md"], ["target.md"])

    assert metrics["rank"] == 2
    assert metrics["hit"] == 1.0
    assert metrics["recall"] == 1.0
    assert metrics["mrr"] == pytest.approx(0.5)
    assert metrics["ndcg"] == pytest.approx(1.0 / math.log2(3))


def test_ranked_metrics_multiple_relevant_documents():
    metrics = benchmark.ranked_metrics(
        ["a.md", "noise.md", "b.md"],
        ["a.md", "b.md"],
    )
    ideal = 1.0 + 1.0 / math.log2(3)
    observed = 1.0 + 1.0 / math.log2(4)

    assert metrics["hit"] == 1.0
    assert metrics["recall"] == 1.0
    assert metrics["mrr"] == 1.0
    assert metrics["ndcg"] == pytest.approx(observed / ideal)


def test_ranked_metrics_miss_and_no_answer():
    miss = benchmark.ranked_metrics(["other.md"], ["target.md"])
    no_answer = benchmark.ranked_metrics(["other.md"], [])

    assert miss == {
        "rank": None, "accuracy": 0.0, "precision": 0.0, "recall": 0.0,
        "f1": 0.0, "hit": 0.0, "mrr": 0.0, "ndcg": 0.0,
    }
    assert no_answer == miss


def test_canonical_path_collapses_duplicate_export_suffix():
    assert benchmark.canonical_path("concepts/example--2.md") == "concepts/example.md"
    assert benchmark.canonical_path("concepts/example.md") == "concepts/example.md"
