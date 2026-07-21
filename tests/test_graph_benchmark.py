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
    assert metrics["retrieved_targets"] == 1
    assert metrics["first_hit_cost"] == 2


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
        "retrieved_targets": 0, "first_hit_cost": benchmark.TOP_K + 1,
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
    assert audit["frontmatter_count"] == 1
    assert audit["exact_query_overlap_ids"] == ["E01"]
    assert (bundle / "events" / "one.md").is_file()
    assert not (bundle / "events" / "two.md").exists()


def test_corpus_expansion_chart_labels_both_conditions():
    summary = {stage: {"recall": 0.5} for stage in benchmark.STAGES}
    expanded = {stage: {"recall": 0.4} for stage in benchmark.STAGES}

    output = benchmark.corpus_expansion_svg(summary, expanded)

    assert "Macro Recall@10" in output
    assert output.count("-0.100") == len(benchmark.STAGES)


def test_corpus_statement_separates_labels_from_event_stress_pages():
    manifest = {
        "base_page_count": 142,
        "bundle_page_count": 219,
        "event_corpus": {
            "archive_name": "events.zip",
            "page_count": 77,
            "unique_body_count": 77,
            "frontmatter_count": 77,
            "event_date_range": ["2026-07-13", "2026-07-21"],
            "top_tags": [["ai-news", 77]],
        },
    }

    output = benchmark.corpus_statement_html(manifest)

    assert "80 qrels belong to the base corpus" in output
    assert "Unjudged topical stress documents" in output
    assert "Frozen-target retention" in output


def test_metric_design_excludes_sparse_classification_metrics_from_headline():
    output = benchmark.metric_design_html()

    assert "Macro Recall@10" in output
    assert "Query Success@10" in output
    assert "First-hit pages" in output
    assert "Precision@10" in output
    assert "excluded from the headline" in output


def test_summary_reports_recovery_success_and_reading_cost():
    rows = [
        {"relevant_paths": ["a.md"], "candidate_paths": ["a.md"], "retrieved_targets": 1,
         "first_hit_cost": 1, "hit": 1.0, "ndcg": 1.0, "accuracy": 1.0,
         "precision": 0.1, "recall": 1.0, "f1": 2 / 11, "mrr": 1.0,
         "false_positive": False, "latency_ms": 1.0},
        {"relevant_paths": ["b.md"], "candidate_paths": [], "retrieved_targets": 0,
         "first_hit_cost": 11, "hit": 0.0, "ndcg": 0.0, "accuracy": 0.0,
         "precision": 0.0, "recall": 0.0, "f1": 0.0, "mrr": 0.0,
         "false_positive": False, "latency_ms": 2.0},
    ]

    output = benchmark.summarize(rows)

    assert output["recall"] == 0.5
    assert output["success"] == 0.5
    assert output["target_retrieved_count"] == 1
    assert output["target_total_count"] == 2
    assert output["first_hit_cost"] == 6.0
    assert output["missed_query_count"] == 1
