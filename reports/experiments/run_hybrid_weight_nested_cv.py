#!/usr/bin/env python3
"""Run fine-grid, repeated grouped nested CV for Mneme Hybrid weights."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import random
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[2]
PILOT_PATH = ROOT / "reports" / "experiments" / "run_hybrid_weight_ablation.py"
SPEC = importlib.util.spec_from_file_location("hybrid_weight_pilot", PILOT_PATH)
assert SPEC and SPEC.loader
pilot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pilot)

SEED = 20260723
GRID_STEP = 0.01
REPEATS = 10
FOLDS = 5
BOOTSTRAP_RUNS = 10_000
LEGS = ("graph", "fts5", "l2")
FAMILIES = pilot.FAMILIES
CURRENT = {"graph": 0.4, "fts5": 0.4, "l2": 0.2}


def weight_grid(active_legs: tuple[str, ...], step: float = GRID_STEP) -> list[dict[str, float]]:
    units = round(1.0 / step)
    output = []
    if len(active_legs) == 1:
        return [{leg: float(leg == active_legs[0]) for leg in LEGS}]
    for graph_units in range(units + 1):
        for fts_units in range(units - graph_units + 1):
            l2_units = units - graph_units - fts_units
            values = {"graph": graph_units, "fts5": fts_units, "l2": l2_units}
            if all(values[leg] > 0 for leg in active_legs) and all(
                values[leg] == 0 for leg in LEGS if leg not in active_legs
            ):
                output.append({leg: values[leg] / units for leg in LEGS})
    return output


def grouped_folds(
    queries: list[dict[str, Any]], repeats: int = REPEATS, folds: int = FOLDS
) -> list[dict[str, int]]:
    source_by_group = {query["base_id"]: query["source"] for query in queries}
    groups_by_source: dict[str, list[str]] = defaultdict(list)
    for group, source in source_by_group.items():
        groups_by_source[source].append(group)
    assignments = []
    for repeat in range(repeats):
        current: dict[str, int] = {}
        for source, groups in sorted(groups_by_source.items()):
            ordered = sorted(groups)
            source_seed = int(hashlib.sha256(source.encode()).hexdigest()[:8], 16)
            random.Random(SEED + repeat * 1009 + source_seed).shuffle(ordered)
            for index, group in enumerate(ordered):
                current[group] = index % folds
        assignments.append(current)
    return assignments


def statistical_query_indices(queries: list[dict[str, Any]]) -> list[int]:
    return [
        index for index, query in enumerate(queries)
        if not (query["source"] == "title" and query["family"] == "exact")
    ]


def title_contract_indices(queries: list[dict[str, Any]]) -> list[int]:
    return [
        index for index, query in enumerate(queries)
        if query["source"] == "title" and query["family"] == "exact"
    ]


def build_metric_grid(
    queries: list[dict[str, Any]],
    cache: dict[str, Any],
    weights: list[dict[str, float]],
    active_legs: tuple[str, ...],
) -> dict[str, Any]:
    import numpy as np

    weight_matrix = np.asarray([[item[leg] for leg in LEGS] for item in weights], dtype=np.float32)
    shape = (len(weights), len(queries))
    metrics = {name: np.zeros(shape, dtype=np.float32) for name in ("hit1", "mrr", "recall3", "recall10")}
    for query_index, query in enumerate(queries):
        legs = cache[query["id"]]
        paths = sorted({item["path"] for leg in active_legs for item in legs.get(leg, [])})
        if not paths:
            continue
        path_index = {path: index for index, path in enumerate(paths)}
        components = np.zeros((len(paths), len(LEGS)), dtype=np.float32)
        for rank, item in enumerate(legs.get("graph", []), 1):
            if "graph" in active_legs and item["path"] in path_index:
                components[path_index[item["path"]], 0] = float(item.get("graph_score", 0.0))
        for leg_index, leg in ((1, "fts5"), (2, "l2")):
            if leg not in active_legs:
                continue
            for rank, item in enumerate(legs.get(leg, []), 1):
                if item["path"] in path_index:
                    components[path_index[item["path"]], leg_index] = 1.0 / rank
        # Production rounds fused scores to six decimals before ordering.
        scores = np.round(weight_matrix @ components.T, 6)
        order = np.argsort(-scores, axis=1, kind="stable")
        relevant = np.asarray([path in set(query["relevant_paths"]) for path in paths], dtype=bool)
        ordered_relevant = relevant[order]
        any_hit = ordered_relevant.any(axis=1)
        first = np.argmax(ordered_relevant, axis=1) + 1
        metrics["hit1"][:, query_index] = ordered_relevant[:, 0]
        metrics["mrr"][:, query_index] = np.where(any_hit, 1.0 / first, 0.0)
        denominator = max(1, len(query["relevant_paths"]))
        metrics["recall3"][:, query_index] = ordered_relevant[:, :3].sum(axis=1) / denominator
        metrics["recall10"][:, query_index] = ordered_relevant[:, :10].sum(axis=1) / denominator
    return {"weights": weights, "weight_matrix": weight_matrix, "metrics": metrics, "active_legs": active_legs}


def _mean_by_family(matrix: Any, queries: list[dict[str, Any]], indices: list[int]) -> tuple[Any, Any]:
    import numpy as np

    family_means = []
    for family in FAMILIES:
        selected = [index for index in indices if queries[index]["family"] == family]
        if selected:
            family_means.append(matrix[:, selected].mean(axis=1))
    stacked = np.stack(family_means, axis=1)
    return stacked.mean(axis=1), stacked.min(axis=1)


def select_weight(
    grid: dict[str, Any],
    queries: list[dict[str, Any]],
    train_indices: list[int],
    contract_indices: list[int],
) -> tuple[int, dict[str, float]]:
    import numpy as np

    metrics = grid["metrics"]
    contract = metrics["hit1"][:, contract_indices].mean(axis=1)
    family_macro, worst_family = _mean_by_family(metrics["mrr"], queries, train_indices)
    recall3 = metrics["recall3"][:, train_indices].mean(axis=1)
    active = grid["active_legs"]
    target = CURRENT if len(active) == 3 else {
        leg: (1.0 / len(active) if leg in active else 0.0) for leg in LEGS
    }
    distance = np.asarray([
        sum(abs(weight[leg] - target[leg]) for leg in LEGS) for weight in grid["weights"]
    ])
    candidates = np.arange(len(grid["weights"]))
    for values, maximize in (
        (contract, True), (family_macro, True), (worst_family, True),
        (recall3, True), (distance, False),
    ):
        subset = values[candidates]
        target_value = subset.max() if maximize else subset.min()
        candidates = candidates[np.isclose(subset, target_value, atol=1e-10, rtol=0)]
    if len(candidates) > 1:
        candidates = sorted(
            (int(index) for index in candidates),
            key=lambda index: (
                grid["weights"][index]["l2"], grid["weights"][index]["fts5"],
                grid["weights"][index]["graph"],
            ),
            reverse=True,
        )
    selected = int(candidates[0])
    diagnostics = {
        "title_contract_hit1": float(contract[selected]),
        "family_macro_mrr": float(family_macro[selected]),
        "worst_family_mrr": float(worst_family[selected]),
        "recall3": float(recall3[selected]),
    }
    return selected, diagnostics


def append_predictions(
    destination: dict[str, dict[str, list[float]]],
    grid: dict[str, Any],
    weight_index: int,
    queries: list[dict[str, Any]],
    query_indices: Iterable[int],
) -> None:
    for query_index in query_indices:
        query_id = queries[query_index]["id"]
        for metric, matrix in grid["metrics"].items():
            destination[query_id][metric].append(float(matrix[weight_index, query_index]))


def fixed_predictions(
    grid: dict[str, Any], weight_index: int, queries: list[dict[str, Any]], indices: list[int]
) -> dict[str, dict[str, list[float]]]:
    output: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    append_predictions(output, grid, weight_index, queries, indices)
    return output


def prediction_rows(
    predictions: dict[str, dict[str, list[float]]], queries: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    query_by_id = {query["id"]: query for query in queries}
    rows = []
    for query_id, values in predictions.items():
        query = query_by_id[query_id]
        rows.append({
            "id": query_id, "base_id": query["base_id"], "family": query["family"],
            "source": query["source"], "query": query["query"],
            **{metric: statistics.fmean(samples) for metric, samples in values.items()},
        })
    return sorted(rows, key=lambda row: row["id"])


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[row["base_id"]].append(row)
    group_mrr = {group: statistics.fmean(row["mrr"] for row in items) for group, items in groups.items()}
    family = {
        name: statistics.fmean(row["mrr"] for row in rows if row["family"] == name)
        for name in FAMILIES
    }
    clean = [row["mrr"] for row in rows if row["family"] in {"exact", "long_phrase", "sentence"}]
    noisy = [row["mrr"] for row in rows if row["family"] in {"typo", "omission"}]
    return {
        "case_count": len(groups), "query_count": len(rows),
        "case_macro_mrr": statistics.fmean(group_mrr.values()),
        "family_macro_mrr": statistics.fmean(family.values()),
        "worst_family_mrr": min(family.values()),
        "hit1": statistics.fmean(row["hit1"] for row in rows),
        "recall3": statistics.fmean(row["recall3"] for row in rows),
        "recall10": statistics.fmean(row["recall10"] for row in rows),
        "clean_mrr": statistics.fmean(clean), "noisy_mrr": statistics.fmean(noisy),
        "noise_delta": statistics.fmean(noisy) - statistics.fmean(clean),
        "by_family_mrr": family, "case_mrr": group_mrr,
    }


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, round((len(ordered) - 1) * q)))]


def cluster_bootstrap(
    rows: list[dict[str, Any]], baseline_rows: list[dict[str, Any]] | None = None
) -> dict[str, float]:
    summary = summarize(rows)
    values = summary["case_mrr"]
    baseline = summarize(baseline_rows)["case_mrr"] if baseline_rows else None
    groups = sorted(values)
    rng = random.Random(SEED)
    samples = []
    for _ in range(BOOTSTRAP_RUNS):
        drawn = [groups[rng.randrange(len(groups))] for _ in groups]
        score = statistics.fmean(values[group] for group in drawn)
        if baseline is not None:
            score -= statistics.fmean(baseline[group] for group in drawn)
        samples.append(score)
    return {
        "estimate": summary["case_macro_mrr"] - (
            summarize(baseline_rows)["case_macro_mrr"] if baseline_rows else 0.0
        ),
        "low": percentile(samples, 0.025), "high": percentile(samples, 0.975),
    }


def weight_key(weight: dict[str, float]) -> str:
    return "/".join(f"{weight[leg]:.2f}" for leg in LEGS)


def weight_stability(selected: list[dict[str, float]]) -> dict[str, Any]:
    counts = Counter(weight_key(weight) for weight in selected)
    return {
        "unique_count": len(counts), "top": counts.most_common(10),
        "channel_mean": {leg: statistics.fmean(weight[leg] for weight in selected) for leg in LEGS},
        "channel_stdev": {
            leg: statistics.stdev(weight[leg] for weight in selected) if len(selected) > 1 else 0.0
            for leg in LEGS
        },
    }


def find_weight_index(grid: dict[str, Any], target: dict[str, float]) -> int:
    for index, weight in enumerate(grid["weights"]):
        if all(math.isclose(weight[leg], target[leg], abs_tol=1e-10) for leg in LEGS):
            return index
    raise ValueError(f"weight not in grid: {target}")


def render_report(payload: dict[str, Any]) -> str:
    stages = payload["stages"]
    current = stages["Current triple"]
    tuned = stages["Nested tuned triple"]
    decision = payload["decision"]
    lines = [
        "# Hybrid Weight Nested Cross-Validation Report", "",
        f"> Generated {payload['generated_at']}. This report supersedes the single-split pilot for deployment decisions.", "",
        "## Executive conclusion", "",
        f"The 1% all-data fit selected **{weight_key(payload['final_fit']['triple']['weights'])}**. Across 10x5 grouped outer folds, the tuned procedure reached case-macro MRR@10 **{tuned['summary']['case_macro_mrr']:.3f}** versus **{current['summary']['case_macro_mrr']:.3f}** for 0.40/0.40/0.20. The paired case-cluster bootstrap delta was **{payload['inference']['triple_vs_current']['estimate']:+.3f}** [{payload['inference']['triple_vs_current']['low']:+.3f}, {payload['inference']['triple_vs_current']['high']:+.3f}].", "",
        (f"The preregistered rule recommends changing production to **{weight_key(decision['recommended_weights'])}**."
         if decision["adopt_final_fit"] else f"The preregistered rule does not establish an improvement, so production remains **{weight_key(decision['recommended_weights'])}**."), "",
        "## Out-of-fold comparison", "",
        "| Stage | Case MRR | Family MRR | Worst family | Hit@1 | Recall@3 | Recall@10 | Noisy MRR |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, stage in stages.items():
        score = stage["summary"]
        lines.append(
            f"| {name} | {score['case_macro_mrr']:.3f} | {score['family_macro_mrr']:.3f} | "
            f"{score['worst_family_mrr']:.3f} | {score['hit1']:.3f} | {score['recall3']:.3f} | "
            f"{score['recall10']:.3f} | {score['noisy_mrr']:.3f} |"
        )
    lines += ["", "## Inference", ""]
    for name, interval in payload["inference"].items():
        lines.append(f"- `{name}`: {interval['estimate']:+.3f} [{interval['low']:+.3f}, {interval['high']:+.3f}]")
    stability = payload["stability"]["triple"]
    lines += [
        "", "## Weight stability", "",
        f"The triple tuner selected {stability['unique_count']} distinct weights over {REPEATS * FOLDS} outer folds. Channel means were Graph {stability['channel_mean']['graph']:.3f}, FTS5 {stability['channel_mean']['fts5']:.3f}, L2 {stability['channel_mean']['l2']:.3f}; standard deviations were {stability['channel_stdev']['graph']:.3f}, {stability['channel_stdev']['fts5']:.3f}, and {stability['channel_stdev']['l2']:.3f}.", "",
        "Most frequent selections:", "",
    ]
    lines.extend(f"- `{weight}`: {count}/50 folds" for weight, count in stability["top"])
    lines += [
        "", "## Dataset and execution", "",
        f"- {payload['environment']['base_case_count']} base cases; {payload['environment']['statistical_query_count']} statistical queries; {payload['environment']['title_contract_count']} exact-title contract rows",
        f"- Full triple grid: {payload['parameters']['triple_grid_count']:,}; pair grids: {payload['parameters']['pair_grid_count']:,}; repeats/folds: {REPEATS}x{FOLDS}",
        f"- Query-leg errors: {len(payload['errors'])}; model: `{payload['environment']['embedding_model']}`",
        "", "## Limits", "",
        "This remains a small construction-aware local benchmark over nine concept pages. Nested validation and case-cluster uncertainty prevent variant leakage and reduce tuning optimism, but they do not replace independent human queries or production search logs. Re-run after material corpus, enrichment, model, threshold, or scoring changes.", "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle")
    parser.add_argument("--output", type=Path, default=ROOT / "reports" / "experiments" / "hybrid-weight-nested-cv.results.json")
    parser.add_argument("--report", type=Path, default=ROOT / "reports" / "experiments" / "hybrid-weight-nested-cv-report.md")
    args = parser.parse_args()
    bundle = pilot.resolve_bundle(args.bundle)
    manifest_path = bundle / ".mneme" / "graph-extractions.json"
    entities = pilot.load_entities(manifest_path)
    queries = pilot.build_queries(bundle, entities)
    cache, errors = pilot.retrieve_legs(bundle, queries)
    stat_indices = statistical_query_indices(queries)
    contract_indices = title_contract_indices(queries)

    grids = {
        "triple": build_metric_grid(queries, cache, weight_grid(LEGS), LEGS),
        "graph_fts5": build_metric_grid(queries, cache, weight_grid(("graph", "fts5")), ("graph", "fts5")),
        "graph_l2": build_metric_grid(queries, cache, weight_grid(("graph", "l2")), ("graph", "l2")),
        "fts5_l2": build_metric_grid(queries, cache, weight_grid(("fts5", "l2")), ("fts5", "l2")),
        "graph": build_metric_grid(queries, cache, weight_grid(("graph",)), ("graph",)),
        "fts5": build_metric_grid(queries, cache, weight_grid(("fts5",)), ("fts5",)),
        "l2": build_metric_grid(queries, cache, weight_grid(("l2",)), ("l2",)),
        "equal": build_metric_grid(queries, cache, [{"graph": 1/3, "fts5": 1/3, "l2": 1/3}], LEGS),
    }
    assignments = grouped_folds(queries)
    tuned_names = {
        "Nested tuned triple": "triple",
        "Nested tuned Graph+FTS5": "graph_fts5",
        "Nested tuned Graph+L2": "graph_l2",
        "Nested tuned FTS5+L2": "fts5_l2",
    }
    predictions: dict[str, Any] = {
        name: defaultdict(lambda: defaultdict(list)) for name in tuned_names
    }
    fold_records = []
    selected_weights: dict[str, list[dict[str, float]]] = defaultdict(list)
    for repeat, assignment in enumerate(assignments):
        for fold in range(FOLDS):
            train = [index for index in stat_indices if assignment[queries[index]["base_id"]] != fold]
            test = [index for index in stat_indices if assignment[queries[index]["base_id"]] == fold]
            record = {"repeat": repeat, "fold": fold, "test_base_ids": sorted({queries[index]["base_id"] for index in test}), "selections": {}}
            for stage_name, grid_name in tuned_names.items():
                grid = grids[grid_name]
                selected, diagnostics = select_weight(grid, queries, train, contract_indices)
                weight = grid["weights"][selected]
                selected_weights[grid_name].append(weight)
                append_predictions(predictions[stage_name], grid, selected, queries, test)
                record["selections"][grid_name] = {"weights": weight, "train": diagnostics}
            fold_records.append(record)
    current_index = find_weight_index(grids["triple"], CURRENT)
    fixed = {
        "Current triple": fixed_predictions(grids["triple"], current_index, queries, stat_indices),
        "Equal triple": fixed_predictions(grids["equal"], 0, queries, stat_indices),
        "Graph only": fixed_predictions(grids["graph"], 0, queries, stat_indices),
        "FTS5 only": fixed_predictions(grids["fts5"], 0, queries, stat_indices),
        "L2 only": fixed_predictions(grids["l2"], 0, queries, stat_indices),
    }
    predictions.update(fixed)
    stage_rows = {name: prediction_rows(values, queries) for name, values in predictions.items()}
    stages = {name: {"summary": summarize(rows), "rows": rows} for name, rows in stage_rows.items()}
    strongest_pair = max(
        (name for name in tuned_names if name != "Nested tuned triple"),
        key=lambda name: stages[name]["summary"]["case_macro_mrr"],
    )
    inference = {
        "triple_mrr": cluster_bootstrap(stage_rows["Nested tuned triple"]),
        "triple_vs_current": cluster_bootstrap(stage_rows["Nested tuned triple"], stage_rows["Current triple"]),
        "triple_vs_best_pair": cluster_bootstrap(stage_rows["Nested tuned triple"], stage_rows[strongest_pair]),
    }
    final_fit = {}
    for name in ("triple", "graph_fts5", "graph_l2", "fts5_l2"):
        selected, diagnostics = select_weight(grids[name], queries, stat_indices, contract_indices)
        final_fit[name] = {"weights": grids[name]["weights"][selected], "training": diagnostics}
    final_weight = final_fit["triple"]["weights"]
    adopt = (
        final_fit["triple"]["training"]["title_contract_hit1"] == 1.0
        and inference["triple_vs_current"]["low"] > 0
        and inference["triple_vs_best_pair"]["low"] <= 0 <= inference["triple_vs_best_pair"]["high"]
    )
    with pilot.sqlite3.connect(pilot.indexlib.l2_index_path(bundle)) as conn:
        l2_meta = dict(conn.execute("SELECT key,value FROM meta").fetchall())
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "protocol": "reports/designs/2026-07-23-hybrid-weight-nested-cv.md",
        "environment": {
            "bundle": str(bundle), "base_case_count": len({query["base_id"] for query in queries}),
            "statistical_query_count": len(stat_indices), "title_contract_count": len(contract_indices),
            "embedding_model": l2_meta.get("embedding_model", "unknown"),
            "index_sha256": {
                "graph": pilot.sha256_file(pilot.graphlib.graph_index_path(bundle)),
                "fts5": pilot.sha256_file(pilot.indexlib.fts_index_path(bundle)),
                "l2": pilot.sha256_file(pilot.indexlib.l2_index_path(bundle)),
                "extractions": pilot.sha256_file(manifest_path),
            },
        },
        "parameters": {
            "seed": SEED, "grid_step": GRID_STEP, "repeats": REPEATS, "folds": FOLDS,
            "bootstrap_runs": BOOTSTRAP_RUNS, "triple_grid_count": len(grids["triple"]["weights"]),
            "pair_grid_count": sum(len(grids[name]["weights"]) for name in ("graph_fts5", "graph_l2", "fts5_l2")),
        },
        "errors": errors, "folds": fold_records, "stages": stages,
        "stability": {name: weight_stability(weights) for name, weights in selected_weights.items()},
        "final_fit": final_fit, "strongest_pair": strongest_pair, "inference": inference,
        "decision": {"adopt_final_fit": adopt, "recommended_weights": final_weight if adopt else CURRENT},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.report.write_text(render_report(payload), encoding="utf-8")
    print(args.report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
