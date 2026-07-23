from __future__ import annotations

import importlib.util
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "reports" / "experiments" / "run_hybrid_weight_nested_cv.py"
SPEC = importlib.util.spec_from_file_location("hybrid_weight_nested_cv", SCRIPT)
assert SPEC and SPEC.loader
benchmark = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(benchmark)


def sample_queries():
    rows = []
    for source, count in (("entity", 7), ("pair", 6), ("title", 5)):
        for group_index in range(count):
            for family in benchmark.FAMILIES:
                rows.append({
                    "id": f"{source}-{group_index}:{family}",
                    "base_id": f"{source}-{group_index}",
                    "source": source,
                    "family": family,
                })
    return rows


def test_one_percent_grid_counts_every_positive_simplex_point():
    triple = benchmark.weight_grid(benchmark.LEGS)
    pair = benchmark.weight_grid(("graph", "l2"))

    assert len(triple) == 4851
    assert len(pair) == 99
    assert all(abs(sum(weight.values()) - 1.0) < 1e-12 for weight in triple + pair)


def test_grouped_folds_keep_variants_together_and_cover_each_group_once():
    queries = sample_queries()
    assignments = benchmark.grouped_folds(queries, repeats=3, folds=5)

    assert len(assignments) == 3
    groups = {query["base_id"] for query in queries}
    assert all(set(assignment) == groups for assignment in assignments)
    for assignment in assignments:
        counts = Counter(assignment.values())
        assert set(counts) == set(range(5))
        assert max(counts.values()) - min(counts.values()) <= 2


def test_exact_title_contract_is_excluded_from_statistical_rows():
    queries = sample_queries()
    statistical = benchmark.statistical_query_indices(queries)
    contract = benchmark.title_contract_indices(queries)

    assert len(contract) == 5
    assert not set(statistical) & set(contract)
    assert len(statistical) + len(contract) == len(queries)


def test_cluster_bootstrap_resamples_base_cases_not_query_variants():
    rows = [
        {"id": f"a:{family}", "base_id": "a", "family": family, "mrr": 1.0,
         "hit1": 1.0, "recall3": 1.0, "recall10": 1.0}
        for family in benchmark.FAMILIES
    ] + [
        {"id": f"b:{family}", "base_id": "b", "family": family, "mrr": 0.0,
         "hit1": 0.0, "recall3": 0.0, "recall10": 0.0}
        for family in benchmark.FAMILIES
    ]

    interval = benchmark.cluster_bootstrap(rows)

    assert interval["estimate"] == 0.5
    assert interval["low"] == 0.0
    assert interval["high"] == 1.0
