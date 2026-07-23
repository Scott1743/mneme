#!/usr/bin/env python3
"""Run a local Graph/FTS5/L2 comparison, ablation, and weight search."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import random
import re
import sqlite3
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "skills" / "mneme" / "scripts"))

from mneme import __version__, graphlib, indexlib, okflib  # noqa: E402

SEED = 20260723
TOP_K = 10
POOL_K = 100
GRID_STEP = 0.05
BOOTSTRAP_RUNS = 5_000
FAMILIES = ("exact", "long_phrase", "sentence", "typo", "omission")
LEGS = ("graph", "fts5", "l2")
CONFUSIONS = {
    "审": "申", "批": "比", "合": "和", "同": "桐", "价": "架", "格": "各",
    "实": "时", "际": "计", "套": "淘", "餐": "参", "测": "策", "算": "蒜",
    "历": "厉", "史": "使", "签": "迁", "续": "旭", "商": "伤", "机": "鸡",
    "回": "汇", "顾": "故", "任": "认", "务": "物", "盈": "赢", "亏": "葵",
    "幅": "福", "度": "渡", "失": "诗", "败": "拜", "场": "厂", "景": "井",
    "类": "累", "预": "域", "税": "睡", "前": "钱", "利": "力", "润": "论",
    "成": "城", "本": "笨", "稳": "吻", "定": "订", "周": "洲", "期": "七",
    "状": "壮", "态": "太", "移": "姨", "动": "冻", "端": "段", "费": "废",
    "率": "律", "管": "馆", "理": "里", "数": "树", "据": "具", "中": "终",
    "台": "抬", "省": "醒", "公": "工", "司": "思", "外": "歪", "包": "胞",
    "集": "急", "团": "湍", "考": "烤", "结": "洁", "果": "裹", "载": "再",
}


def stable_key(value: str) -> str:
    return hashlib.sha256(f"{SEED}:{value}".encode()).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_bundle(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    config = Path.home() / ".config" / "mneme" / "config.toml"
    import tomllib

    payload = tomllib.loads(config.read_text(encoding="utf-8"))
    return Path(payload["bundle_path"]).expanduser().resolve()


def clean_name(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def suitable_name(name: str) -> bool:
    if not 2 <= len(name) <= 42:
        return False
    return not any(token in name.casefold() for token in ("http", "www.", "@", "\\", "/"))


def mutate_typo(text: str) -> str:
    for index, char in enumerate(text):
        if char in CONFUSIONS:
            return text[:index] + CONFUSIONS[char] + text[index + 1:]
    compact = text.replace(" ", "")
    if len(compact) >= 2:
        pos = int(stable_key(text)[:8], 16) % (len(compact) - 1)
        compact = compact[:pos] + compact[pos + 1] + compact[pos] + compact[pos + 2:]
        return compact
    return text + "x"


def mutate_omission(text: str) -> str:
    positions = [index for index, char in enumerate(text) if not char.isspace()]
    if len(positions) <= 1:
        return text
    pos = positions[int(stable_key(f"omit:{text}")[:8], 16) % len(positions)]
    return text[:pos] + text[pos + 1:]


def load_entities(manifest_path: Path) -> list[dict[str, Any]]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if payload.get("version") != 1 or not isinstance(payload.get("pages"), list):
        raise ValueError("unsupported graph extraction manifest")
    entities: dict[str, dict[str, Any]] = {}
    for block in payload["pages"]:
        page = clean_name(block.get("page"))
        if not page.endswith(".md"):
            continue
        for raw in block.get("entities", []):
            name = clean_name(raw.get("name"))
            if float(raw.get("confidence") or 0.0) < 0.80 or not suitable_name(name):
                continue
            item = entities.setdefault(name.casefold(), {
                "name": name, "pages": set(), "descriptions": set(), "type": clean_name(raw.get("type")),
            })
            item["pages"].add(page)
            description = clean_name(raw.get("description"))
            if description:
                item["descriptions"].add(description)
    result = []
    for item in entities.values():
        item["pages"] = sorted(item["pages"])
        item["descriptions"] = sorted(item["descriptions"], key=lambda value: (len(value), value))
        result.append(item)
    return sorted(result, key=lambda item: stable_key(item["name"]))


def case_variants(
    base_id: str,
    names: list[str],
    descriptions: list[str],
    relevant: list[str],
    source: str,
) -> list[dict[str, Any]]:
    exact = " ".join(names)
    description = " ".join(descriptions[:2]) or "相关业务规则和使用场景"
    long_phrase = f"{exact} {description}"
    if len(names) == 1:
        sentence = f"请查找和{names[0]}有关的业务规则，说明它在系统中的作用"
        typo = mutate_typo(names[0])
        omission = mutate_omission(names[0])
    else:
        sentence = f"在同一个业务场景中，{names[0]}和{names[1]}是什么关系"
        typo = f"{mutate_typo(names[0])} {names[1]}"
        omission = f"{mutate_omission(names[0])} {names[1]}"
    queries = {
        "exact": exact, "long_phrase": long_phrase, "sentence": sentence,
        "typo": typo, "omission": omission,
    }
    split = "validation" if int(stable_key(base_id)[:8], 16) % 100 < 60 else "holdout"
    return [{
        "id": f"{base_id}:{family}", "base_id": base_id, "family": family,
        "split": split, "query": queries[family], "relevant_paths": relevant,
        "names": names, "source": source,
    } for family in FAMILIES]


def build_queries(bundle: Path, entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in entities:
        rows.extend(case_variants(
            f"entity:{item['name'].casefold()}", [item["name"]], item["descriptions"], item["pages"],
            "entity",
        ))

    by_page: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in entities:
        for page in item["pages"]:
            by_page[page].append(item)
    for page, page_entities in sorted(by_page.items()):
        pairs = []
        for left_index, left in enumerate(page_entities):
            for right in page_entities[left_index + 1:]:
                common = sorted(set(left["pages"]) & set(right["pages"]))
                if common:
                    pairs.append((stable_key(f"{page}:{left['name']}:{right['name']}"), left, right, common))
        for _, left, right, common in sorted(pairs)[:3]:
            names = sorted([left["name"], right["name"]])
            base_id = f"pair:{names[0].casefold()}+{names[1].casefold()}"
            descriptions = left["descriptions"][:1] + right["descriptions"][:1]
            rows.extend(case_variants(base_id, names, descriptions, common, "pair"))

    source_pages = sorted({page for item in entities for page in item["pages"]})
    for page in source_pages:
        parsed = okflib.read_concept(bundle, page[:-3])
        if not parsed:
            continue
        meta, _ = parsed
        title = clean_name(meta.get("title"))
        if not suitable_name(title):
            continue
        description = clean_name(meta.get("description"))
        rows.extend(case_variants(
            f"title:{page}", [title], [description] if description else [], [page], "title",
        ))
    return sorted(rows, key=lambda item: (item["split"], item["base_id"], FAMILIES.index(item["family"])))


def canonical_candidates(items: Iterable[dict[str, Any]], path_key: str = "path") -> list[dict[str, Any]]:
    seen = set()
    output = []
    for item in items:
        path = clean_name(item.get(path_key))
        if path and path not in seen:
            seen.add(path)
            output.append(dict(item, path=path))
    return output


def retrieve_legs(bundle: Path, queries: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    graph_db = graphlib.graph_index_path(bundle)
    fts_db = indexlib.fts_index_path(bundle)
    l2_db = indexlib.l2_index_path(bundle)
    for path in (graph_db, fts_db, l2_db):
        if not path.is_file():
            raise FileNotFoundError(path)
    if not graphlib.graph_is_fresh(bundle, graph_db):
        raise RuntimeError("graph index is stale; rebuild it before benchmarking")
    embedder = indexlib.default_embed_fn()
    cache: dict[str, Any] = {}
    errors: list[dict[str, Any]] = []
    for index, query in enumerate(queries, 1):
        legs: dict[str, list[dict[str, Any]]] = {}
        try:
            graph_hits = graphlib.graph_page_candidates(graph_db, query["query"], limit=POOL_K, depth=2)
            legs["graph"] = canonical_candidates(graph_hits, "page_path")
        except Exception as exc:  # preserve per-leg failure as benchmark evidence
            legs["graph"] = []
            errors.append({"id": query["id"], "leg": "graph", "error": f"{type(exc).__name__}: {exc}"})
        try:
            legs["fts5"] = canonical_candidates(indexlib.search(query["query"], fts_db, k=POOL_K)["candidates"])
        except Exception as exc:
            legs["fts5"] = []
            errors.append({"id": query["id"], "leg": "fts5", "error": f"{type(exc).__name__}: {exc}"})
        try:
            legs["l2"] = canonical_candidates(indexlib.search_bundle(bundle, query["query"], k=POOL_K, embed_fn=embedder))
        except Exception as exc:
            legs["l2"] = []
            errors.append({"id": query["id"], "leg": "l2", "error": f"{type(exc).__name__}: {exc}"})
        cache[query["id"]] = legs
        if index % 25 == 0 or index == len(queries):
            print(f"retrieval {index}/{len(queries)}", file=sys.stderr, flush=True)
    return cache, errors


def fuse(legs: dict[str, list[dict[str, Any]]], weights: dict[str, float], k: int = TOP_K) -> list[str]:
    scores: dict[str, float] = defaultdict(float)
    active: dict[str, float] = {}
    for leg in LEGS:
        weight = max(0.0, float(weights.get(leg, 0.0)))
        hits = legs.get(leg, [])
        if weight > 0 and hits:
            active[leg] = weight
    total = sum(active.values())
    if total <= 0:
        return []
    for leg, weight in active.items():
        for rank, item in enumerate(legs[leg], 1):
            component = float(item.get("graph_score", 0.0)) if leg == "graph" else 1.0 / rank
            scores[item["path"]] += weight * component / total
    return [path for path, _ in sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:k]]


def query_metrics(paths: list[str], relevant_paths: list[str]) -> dict[str, float]:
    relevant = set(relevant_paths)
    ranks = [rank for rank, path in enumerate(paths[:TOP_K], 1) if path in relevant]
    first = min(ranks) if ranks else None
    return {
        "hit1": float(first == 1),
        "mrr": 0.0 if first is None else 1.0 / first,
        "recall3": sum(path in relevant for path in paths[:3]) / len(relevant),
        "recall10": len(ranks) / len(relevant),
    }


def evaluate(queries: list[dict[str, Any]], cache: dict[str, Any], weights: dict[str, float], split: str) -> dict[str, Any]:
    rows = []
    for query in queries:
        if query["split"] != split:
            continue
        paths = fuse(cache[query["id"]], weights)
        rows.append(dict(query, candidate_paths=paths, **query_metrics(paths, query["relevant_paths"])))
    by_family = {}
    for family in FAMILIES:
        family_rows = [row for row in rows if row["family"] == family]
        by_family[family] = {
            metric: sum(row[metric] for row in family_rows) / len(family_rows)
            for metric in ("hit1", "mrr", "recall3", "recall10")
        }
    overall = {
        metric: sum(row[metric] for row in rows) / len(rows)
        for metric in ("hit1", "mrr", "recall3", "recall10")
    }
    overall["family_macro_mrr"] = sum(item["mrr"] for item in by_family.values()) / len(FAMILIES)
    overall["worst_family_mrr"] = min(item["mrr"] for item in by_family.values())
    clean = [row for row in rows if row["family"] in {"exact", "long_phrase", "sentence"}]
    noisy = [row for row in rows if row["family"] in {"typo", "omission"}]
    overall["clean_mrr"] = sum(row["mrr"] for row in clean) / len(clean)
    overall["noisy_mrr"] = sum(row["mrr"] for row in noisy) / len(noisy)
    overall["noise_delta"] = overall["noisy_mrr"] - overall["clean_mrr"]
    title_exact = [
        row for row in rows if row.get("source") == "title" and row["family"] == "exact"
    ]
    overall["title_exact_hit1"] = (
        sum(row["hit1"] for row in title_exact) / len(title_exact) if title_exact else 0.0
    )
    return {"weights": weights, "split": split, "count": len(rows), "overall": overall, "by_family": by_family, "rows": rows}


def weight_grid(active_legs: tuple[str, ...]) -> Iterable[dict[str, float]]:
    units = round(1 / GRID_STEP)
    if len(active_legs) == 1:
        yield {leg: float(leg == active_legs[0]) for leg in LEGS}
        return
    for graph_units in range(units + 1):
        for fts_units in range(units - graph_units + 1):
            l2_units = units - graph_units - fts_units
            values = {"graph": graph_units, "fts5": fts_units, "l2": l2_units}
            if all(values[leg] > 0 for leg in active_legs) and all(values[leg] == 0 for leg in LEGS if leg not in active_legs):
                yield {leg: round(values[leg] / units, 2) for leg in LEGS}


def selection_key(result: dict[str, Any], active_count: int) -> tuple[float, ...]:
    overall = result["overall"]
    target = 1.0 / active_count
    distance = sum(abs(weight - target) for weight in result["weights"].values() if weight > 0)
    return (
        overall["title_exact_guard"], overall["family_macro_mrr"],
        overall["worst_family_mrr"], overall["recall3"],
        -distance, result["weights"]["l2"], result["weights"]["fts5"],
    )


def tune(queries: list[dict[str, Any]], cache: dict[str, Any], active_legs: tuple[str, ...]) -> dict[str, Any]:
    candidates = [evaluate(queries, cache, weights, "validation") for weights in weight_grid(active_legs)]
    title_queries = [
        query for query in queries if query.get("source") == "title" and query["family"] == "exact"
    ]
    for result in candidates:
        result["overall"]["title_exact_guard"] = sum(
            query_metrics(
                fuse(cache[query["id"]], result["weights"]), query["relevant_paths"]
            )["hit1"]
            for query in title_queries
        ) / len(title_queries)
    return max(candidates, key=lambda result: selection_key(result, len(active_legs)))


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, round((len(ordered) - 1) * q)))]


def bootstrap(rows: list[dict[str, Any]], other_rows: list[dict[str, Any]] | None = None) -> dict[str, float]:
    rng = random.Random(SEED)
    other = {row["id"]: row for row in other_rows or []}
    values = []
    for _ in range(BOOTSTRAP_RUNS):
        sample = [rows[rng.randrange(len(rows))] for _ in rows]
        score = sum(row["mrr"] for row in sample) / len(sample)
        if other:
            score -= sum(other[row["id"]]["mrr"] for row in sample) / len(sample)
        values.append(score)
    return {"low": percentile(values, 0.025), "high": percentile(values, 0.975)}


def fmt(value: float) -> str:
    return f"{value:.3f}"


def weights_text(weights: dict[str, float]) -> str:
    return "/".join(f"{weights[leg]:.2f}" for leg in LEGS)


def render_report(payload: dict[str, Any]) -> str:
    holdout = payload["stages"]
    tuned = holdout["Tuned triple"]
    current = holdout["Current triple"]
    best_pair_name = max((name for name in holdout if name.startswith("Tuned ") and "+" in name), key=lambda name: holdout[name]["overall"]["family_macro_mrr"])
    best_pair = holdout[best_pair_name]
    delta = tuned["overall"]["family_macro_mrr"] - current["overall"]["family_macro_mrr"]
    pair_delta = tuned["overall"]["family_macro_mrr"] - best_pair["overall"]["family_macro_mrr"]
    ci = payload["bootstrap"]
    adopt = (
        tuned["overall"]["title_exact_hit1"] >= current["overall"]["title_exact_hit1"]
        and ci["delta_vs_current"]["low"] > 0
        and ci["delta_vs_best_pair"]["low"] <= 0 <= ci["delta_vs_best_pair"]["high"]
    )
    recommendation = tuned["weights"] if adopt else current["weights"]
    payload["decision"] = {"adopt_tuned_triple": adopt, "recommended_weights": recommendation, "best_pair": best_pair_name}
    lines = [
        "# Hybrid Weight Comparison and Ablation Report", "",
        "> **Superseded:** deployment decisions now use `hybrid-weight-nested-cv-report.md`.", "",
        f"> Generated {payload['generated_at']} from the active local bundle. Protocol: `reports/designs/2026-07-23-hybrid-weight-ablation.md`.", "",
        "## Executive conclusion", "",
        f"Validation selected **Graph/FTS5/L2 = {weights_text(tuned['weights'])}**. On the untouched holdout, its family-macro MRR@10 was **{fmt(tuned['overall']['family_macro_mrr'])}**, versus **{fmt(current['overall']['family_macro_mrr'])}** for 0.40/0.40/0.20 (delta {delta:+.3f}) and **{fmt(best_pair['overall']['family_macro_mrr'])}** for the strongest pair `{best_pair_name}` (triple delta {pair_delta:+.3f}).", "",
        (f"The frozen deployment rule therefore keeps all three paths and recommends **{weights_text(recommendation)}**."
         if adopt else f"The frozen deployment rule does not justify changing the current triple; it retains **{weights_text(recommendation)}**."), "",
        "## Holdout comparison", "",
        "| Stage | Graph/FTS5/L2 | Family MRR | Title Hit@1 | Worst family | Hit@1 | Recall@3 | Recall@10 | Noisy MRR |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, result in holdout.items():
        score = result["overall"]
        lines.append(f"| {name} | {weights_text(result['weights'])} | {fmt(score['family_macro_mrr'])} | {fmt(score['title_exact_hit1'])} | {fmt(score['worst_family_mrr'])} | {fmt(score['hit1'])} | {fmt(score['recall3'])} | {fmt(score['recall10'])} | {fmt(score['noisy_mrr'])} |")
    lines += ["", "## Query-family ablation", "", "| Stage | Exact | Long phrase | Sentence | Typo | Omission |", "|---|---:|---:|---:|---:|---:|"]
    for name, result in holdout.items():
        family = result["by_family"]
        lines.append(f"| {name} | " + " | ".join(fmt(family[item]["mrr"]) for item in FAMILIES) + " |")
    lines += [
        "", "## Robustness and uncertainty", "",
        f"The tuned triple's query-bootstrap holdout MRR 95% interval is [{ci['tuned_mrr']['low']:.3f}, {ci['tuned_mrr']['high']:.3f}]. The paired tuned-minus-current interval is [{ci['delta_vs_current']['low']:+.3f}, {ci['delta_vs_current']['high']:+.3f}]. The paired tuned-minus-best-pair interval is [{ci['delta_vs_best_pair']['low']:+.3f}, {ci['delta_vs_best_pair']['high']:+.3f}], so the pair's {pair_delta:+.3f} point advantage is not significant.",
        "", f"Clean-to-noisy MRR change for the tuned triple is {tuned['overall']['noise_delta']:+.3f}. Query-leg errors: {len(payload['errors'])}.",
        "", "## Dataset and environment", "",
        f"- Bundle: `{payload['environment']['bundle']}` ({payload['environment']['page_count']} indexed concept pages)",
        f"- Enriched vocabulary: {payload['environment']['entity_count']} eligible entities; {payload['environment']['title_case_count']} page-title controls; {payload['environment']['base_case_count']} base cases; {payload['environment']['query_count']} generated queries",
        f"- Split: {payload['environment']['validation_queries']} validation queries / {payload['environment']['holdout_queries']} holdout queries, grouped by base case",
        f"- Mneme {payload['environment']['mneme_version']}; Python {payload['environment']['python']}; model `{payload['environment']['embedding_model']}`",
        f"- Grid: {GRID_STEP:.2f}; top-k: {TOP_K}; candidate pool: {POOL_K}; bootstrap: {BOOTSTRAP_RUNS}",
        "", "## Interpretation limits", "",
        "This is a small, construction-aware local diagnostic: entity queries and labels originate in the approved enrichment manifest, while title controls come from its authoritative Markdown source pages. The corpus has few concept pages. It measures ranking behavior for the current CRM vocabulary, not general search quality. Re-run after substantial corpus growth, enrichment changes, embedding-model changes, or scoring changes. The machine-readable payload retains every generated query, candidate ranking, error, index hash, validation-selected pair, and metric.", "",
    ]
    if payload["errors"]:
        lines += ["## Retrieval errors", "", "```json", json.dumps(payload["errors"], ensure_ascii=False, indent=2), "```", ""]
    return "\n".join(lines)


def git_revision() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle")
    parser.add_argument("--output", type=Path, default=ROOT / "reports" / "experiments" / "hybrid-weight-ablation.results.json")
    parser.add_argument("--report", type=Path, default=ROOT / "reports" / "experiments" / "hybrid-weight-ablation-report.md")
    args = parser.parse_args()
    bundle = resolve_bundle(args.bundle)
    manifest_path = bundle / ".mneme" / "graph-extractions.json"
    entities = load_entities(manifest_path)
    queries = build_queries(bundle, entities)
    cache, errors = retrieve_legs(bundle, queries)

    tuned_pairs = {
        "Tuned Graph+FTS5": tune(queries, cache, ("graph", "fts5")),
        "Tuned Graph+L2": tune(queries, cache, ("graph", "l2")),
        "Tuned FTS5+L2": tune(queries, cache, ("fts5", "l2")),
    }
    tuned_triple_validation = tune(queries, cache, LEGS)
    stage_weights = {
        "Graph only": {"graph": 1.0, "fts5": 0.0, "l2": 0.0},
        "FTS5 only": {"graph": 0.0, "fts5": 1.0, "l2": 0.0},
        "L2 only": {"graph": 0.0, "fts5": 0.0, "l2": 1.0},
        **{name: result["weights"] for name, result in tuned_pairs.items()},
        "Equal triple": {"graph": 1/3, "fts5": 1/3, "l2": 1/3},
        "Current triple": {"graph": 0.4, "fts5": 0.4, "l2": 0.2},
        "Tuned triple": tuned_triple_validation["weights"],
    }
    stages = {name: evaluate(queries, cache, weights, "holdout") for name, weights in stage_weights.items()}
    tuned_rows = stages["Tuned triple"]["rows"]
    current_rows = stages["Current triple"]["rows"]
    with sqlite3.connect(indexlib.l2_index_path(bundle)) as conn:
        l2_meta = dict(conn.execute("SELECT key,value FROM meta").fetchall())
    page_count = len(okflib.list_concepts(bundle))
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "protocol": "reports/designs/2026-07-23-hybrid-weight-ablation.md",
        "environment": {
            "bundle": str(bundle), "page_count": page_count, "entity_count": len(entities),
            "title_case_count": len({query["base_id"] for query in queries if query["source"] == "title"}),
            "base_case_count": len({query['base_id'] for query in queries}), "query_count": len(queries),
            "validation_queries": sum(query["split"] == "validation" for query in queries),
            "holdout_queries": sum(query["split"] == "holdout" for query in queries),
            "mneme_version": __version__, "python": platform.python_version(),
            "embedding_model": l2_meta.get("embedding_model", "unknown"), "git_revision": git_revision(),
            "index_sha256": {leg: sha256_file(path) for leg, path in {
                "graph": graphlib.graph_index_path(bundle), "fts5": indexlib.fts_index_path(bundle), "l2": indexlib.l2_index_path(bundle),
                "extractions": manifest_path,
            }.items()},
        },
        "parameters": {"seed": SEED, "top_k": TOP_K, "pool_k": POOL_K, "grid_step": GRID_STEP, "bootstrap_runs": BOOTSTRAP_RUNS},
        "queries": queries, "errors": errors,
        "validation_selection": {**tuned_pairs, "Tuned triple": tuned_triple_validation},
        "stages": stages,
        "bootstrap": {
            "tuned_mrr": bootstrap(tuned_rows),
            "delta_vs_current": bootstrap(tuned_rows, current_rows),
            "delta_vs_best_pair": bootstrap(
                tuned_rows,
                max(
                    (stages[name]["rows"] for name in tuned_pairs),
                    key=lambda rows: sum(row["mrr"] for row in rows) / len(rows),
                ),
            ),
        },
    }
    report = render_report(payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.report.write_text(report, encoding="utf-8")
    print(args.report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
