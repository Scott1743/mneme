from __future__ import annotations

import importlib.util
import math
import zipfile
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


def test_question_audit_lists_all_families_and_queries():
    qrels = [
        {"id": "E01", "category": "entity_exact", "query": "Entity", "relevant_paths": ["a.md"], "provenance": "entity"},
        {"id": "C01", "category": "entity_context", "query": "Context", "relevant_paths": ["b.md"], "provenance": "context"},
        {"id": "R01", "category": "relation", "query": "A uses B", "relevant_paths": ["c.md"], "provenance": "relation"},
        {"id": "N01", "category": "no_answer", "query": "missing", "relevant_paths": [], "provenance": "control"},
    ]

    output = benchmark.question_audit_html(qrels)

    assert "Exact entity" in output
    assert "Entity context" in output
    assert "Relation" in output
    assert "No-answer control" in output
    assert all(item["query"] in output for item in qrels)


def test_add_event_corpus_copies_only_top_level_markdown(tmp_path):
    archive = tmp_path / "events.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("events/one.md", "---\ntype: Reference\n---\n\nAgentic AI\n")
        handle.writestr("events/nested/two.md", "ignored")
        handle.writestr("__MACOSX/events/._one.md", "ignored")
    bundle = tmp_path / "wiki"
    bundle.mkdir()
    qrels = [{"id": "E01", "query": "Agentic AI", "relevant_paths": ["concept.md"]}]

    audit = benchmark.add_event_corpus(archive, bundle, qrels)

    assert audit["page_count"] == 1
    assert audit["unique_body_count"] == 1
    assert audit["exact_query_overlap_ids"] == ["E01"]
    assert (bundle / "events" / "one.md").is_file()
    assert not (bundle / "events" / "two.md").exists()


def test_corpus_expansion_chart_labels_both_conditions():
    summary = {stage: {"ndcg": 0.5} for stage in benchmark.STAGES}
    expanded = {stage: {"ndcg": 0.4} for stage in benchmark.STAGES}

    output = benchmark.corpus_expansion_svg(summary, expanded)

    assert "circle=base, square=expanded" in output
    assert output.count("-0.100") == len(benchmark.STAGES)
