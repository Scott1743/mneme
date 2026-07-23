from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "reports" / "experiments" / "run_hybrid_weight_ablation.py"
SPEC = importlib.util.spec_from_file_location("hybrid_weight_ablation", SCRIPT)
assert SPEC and SPEC.loader
benchmark = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(benchmark)


def test_typo_and_omission_are_deterministic_and_distinct():
    assert benchmark.mutate_typo("合同审批") == "和同审批"
    assert benchmark.mutate_typo("合同审批") == benchmark.mutate_typo("合同审批")
    assert benchmark.mutate_omission("合同审批") != "合同审批"


def test_variants_share_split_and_relevance():
    rows = benchmark.case_variants(
        "entity:合同", ["合同"], ["业务合同"], ["concepts/a.md"], "entity",
    )

    assert {row["family"] for row in rows} == set(benchmark.FAMILIES)
    assert len({row["split"] for row in rows}) == 1
    assert all(row["relevant_paths"] == ["concepts/a.md"] for row in rows)
    assert all(row["source"] == "entity" for row in rows)
    assert rows[3]["query"] != "合同"
    assert rows[4]["query"] != "合同"


def test_fuse_matches_production_page_score_contract():
    legs = {
        "graph": [{"path": "a.md", "graph_score": 0.5}, {"path": "b.md", "graph_score": 0.4}],
        "fts5": [{"path": "b.md"}, {"path": "a.md"}],
        "l2": [{"path": "c.md"}, {"path": "a.md"}],
    }

    paths = benchmark.fuse(legs, {"graph": 0.4, "fts5": 0.4, "l2": 0.2})

    assert paths == ["b.md", "a.md", "c.md"]


def test_fuse_renormalizes_when_a_leg_has_no_candidates():
    legs = {"graph": [], "fts5": [{"path": "a.md"}], "l2": [{"path": "b.md"}]}

    paths = benchmark.fuse(legs, {"graph": 0.8, "fts5": 0.1, "l2": 0.1})

    assert paths == ["a.md", "b.md"]


def test_weight_grid_contains_only_requested_positive_legs():
    pair = list(benchmark.weight_grid(("graph", "l2")))
    triple = list(benchmark.weight_grid(benchmark.LEGS))

    assert len(pair) == 19
    assert all(item["graph"] > 0 and item["fts5"] == 0 and item["l2"] > 0 for item in pair)
    assert all(all(item[leg] > 0 for leg in benchmark.LEGS) for item in triple)
    assert all(sum(item.values()) == pytest.approx(1.0) for item in pair + triple)


def test_query_metrics_reward_early_relevant_page():
    first = benchmark.query_metrics(["target.md", "other.md"], ["target.md"])
    second = benchmark.query_metrics(["other.md", "target.md"], ["target.md"])

    assert first["mrr"] == 1.0
    assert second["mrr"] == 0.5
    assert first["recall3"] == second["recall3"] == 1.0


def test_selection_key_treats_exact_title_as_hard_guardrail():
    guarded = {
        "weights": {"graph": 0.4, "fts5": 0.4, "l2": 0.2},
        "overall": {"title_exact_guard": 1.0, "family_macro_mrr": 0.7, "worst_family_mrr": 0.5, "recall3": 0.8},
    }
    unguarded = {
        "weights": {"graph": 0.8, "fts5": 0.1, "l2": 0.1},
        "overall": {"title_exact_guard": 0.9, "family_macro_mrr": 0.9, "worst_family_mrr": 0.8, "recall3": 0.9},
    }

    assert benchmark.selection_key(guarded, 3) > benchmark.selection_key(unguarded, 3)
