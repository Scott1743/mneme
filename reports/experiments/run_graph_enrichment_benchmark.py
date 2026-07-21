#!/usr/bin/env python3
"""Build and run the frozen Mneme Graph enrichment benchmark."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import os
import platform
import random
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]
SKILL_SCRIPTS = ROOT / "skills" / "mneme" / "scripts"
sys.path.insert(0, str(SKILL_SCRIPTS))

from mneme import __version__, graphlib, indexlib  # noqa: E402

TOP_K = 10
QUERY_REPEATS = 5
BOOTSTRAP_RUNS = 10_000
SEED = 20260721
STAGES = ("L1", "G0", "G1", "H0", "H1")
STAGE_LABELS = {
    "L1": "FTS5",
    "G0": "Graph deterministic",
    "G1": "Graph enriched",
    "H0": "Hybrid deterministic",
    "H1": "Hybrid enriched",
}
COLORS = {
    "L1": "#3573b8",
    "G0": "#777777",
    "G1": "#238b68",
    "H0": "#c87a18",
    "H1": "#a44a8b",
}
GENERIC = {
    "系统", "平台", "方案", "流程", "数据", "项目", "产品", "功能", "模型", "服务",
    "用户", "文档", "工具", "技术", "应用", "工作流", "agent", "ai", "api",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_key(value: str) -> str:
    return hashlib.sha256(f"{SEED}:{value}".encode("utf-8")).hexdigest()


def canonical_path(path: str) -> str:
    """Collapse duplicate Feishu exports with identical Markdown bodies."""
    return re.sub(r"--2(?=\.md$)", "", path)


def git_revision() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
        capture_output=True, text=True,
    ).stdout.strip()


def suitable_name(value: str) -> bool:
    value = value.strip()
    if not 3 <= len(value) <= 42 or value.casefold() in GENERIC:
        return False
    if any(token in value for token in ("http", "www.", "@", "\\", "/")):
        return False
    digits = sum(char.isdigit() for char in value)
    return digits / len(value) <= 0.3


def clean_context(name: str, description: str) -> str | None:
    text = re.sub(re.escape(name), "", description, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip(" ，。,:：;；-—()（）")
    if not 8 <= len(text) <= 90 or text.casefold() in GENERIC:
        return None
    return text


def load_extractions(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("version") != 1 or not isinstance(payload.get("pages"), list):
        raise ValueError("unsupported graph extraction manifest")
    return payload


def build_qrels(extraction_path: Path) -> list[dict[str, Any]]:
    payload = load_extractions(extraction_path)
    entities: dict[str, dict[str, Any]] = {}
    relations: dict[tuple[str, str, str], dict[str, Any]] = {}

    for block in payload["pages"]:
        page = str(block.get("page", ""))
        if not page.endswith(".md"):
            continue
        for item in block.get("entities", []):
            name = str(item.get("name", "")).strip()
            confidence = float(item.get("confidence") or 0.0)
            if confidence < 0.80 or not suitable_name(name):
                continue
            entity = entities.setdefault(name.casefold(), {
                "name": name,
                "type": str(item.get("type", "concept")),
                "descriptions": [],
                "pages": set(),
                "confidence": confidence,
            })
            entity["pages"].add(canonical_path(page))
            description = str(item.get("description", "")).strip()
            if description:
                entity["descriptions"].append(description)
            entity["confidence"] = max(entity["confidence"], confidence)

        for item in block.get("relations", []):
            subject = str(item.get("subject", "")).strip()
            predicate = str(item.get("predicate", "")).strip()
            obj = str(item.get("object", "")).strip()
            confidence = float(item.get("confidence") or 0.0)
            if confidence < 0.80 or not predicate:
                continue
            if not suitable_name(subject) or not suitable_name(obj):
                continue
            key = (subject.casefold(), predicate.casefold(), obj.casefold())
            relation = relations.setdefault(key, {
                "subject": subject, "predicate": predicate, "object": obj,
                "pages": set(), "confidence": confidence,
            })
            relation["pages"].add(canonical_path(page))
            relation["confidence"] = max(relation["confidence"], confidence)

    entity_candidates = [
        item for item in entities.values()
        if 1 <= len(item["pages"]) <= 8 and item["type"].casefold() not in {"person", "org", "organization"}
    ]
    entity_candidates.sort(key=lambda item: stable_key(f"entity:{item['name']}"))
    selected_entities = entity_candidates[:24]

    context_candidates = []
    for item in entity_candidates:
        for description in sorted(set(item["descriptions"]), key=len):
            query = clean_context(item["name"], description)
            if query:
                context_candidates.append((item, query))
                break
    context_candidates.sort(key=lambda pair: stable_key(f"context:{pair[0]['name']}:{pair[1]}"))
    selected_contexts = context_candidates[:24]

    relation_candidates = list(relations.values())
    relation_candidates.sort(
        key=lambda item: stable_key(f"relation:{item['subject']}:{item['predicate']}:{item['object']}")
    )
    selected_relations = relation_candidates[:24]

    if min(len(selected_entities), len(selected_contexts), len(selected_relations)) < 24:
        raise ValueError("extraction manifest does not contain enough eligible qrels")

    qrels: list[dict[str, Any]] = []
    for index, item in enumerate(selected_entities, 1):
        qrels.append({
            "id": f"E{index:02d}", "category": "entity_exact", "query": item["name"],
            "relevant_paths": sorted(item["pages"]), "provenance": "extraction entity name",
        })
    for index, (item, query) in enumerate(selected_contexts, 1):
        qrels.append({
            "id": f"C{index:02d}", "category": "entity_context", "query": query,
            "relevant_paths": sorted(item["pages"]), "provenance": "entity description without name",
        })
    for index, item in enumerate(selected_relations, 1):
        qrels.append({
            "id": f"R{index:02d}", "category": "relation",
            "query": f"{item['subject']} {item['predicate']} {item['object']}",
            "relevant_paths": sorted(item["pages"]), "provenance": "extraction relation",
        })
    for index in range(1, 9):
        qrels.append({
            "id": f"N{index:02d}", "category": "no_answer",
            "query": f"__mneme_no_answer_{index:02d}_{stable_key(str(index))[:8]}__",
            "relevant_paths": [], "provenance": "synthetic no-answer control",
        })
    return qrels


def write_qrels(path: Path, qrels: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for item in qrels:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")


def read_qrels(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def indexable_paths(bundle: Path) -> list[Path]:
    paths = []
    for path in sorted(bundle.rglob("*.md")):
        parts = path.relative_to(bundle).parts
        if ".mneme" in parts or "sources" in parts or "external-sources" in parts:
            continue
        paths.append(path)
    return paths


def ranked_metrics(paths: list[str], relevant_paths: list[str]) -> dict[str, float | int | None]:
    relevant = set(relevant_paths)
    if not relevant:
        return {"rank": None, "hit": 0.0, "recall": 0.0, "mrr": 0.0, "ndcg": 0.0}
    ranks = [index for index, path in enumerate(paths[:TOP_K], 1) if path in relevant]
    first = min(ranks) if ranks else None
    dcg = sum(1.0 / math.log2(rank + 1) for rank in ranks)
    ideal = sum(1.0 / math.log2(rank + 1) for rank in range(1, min(len(relevant), TOP_K) + 1))
    return {
        "rank": first,
        "hit": float(bool(ranks)),
        "recall": len(ranks) / len(relevant),
        "mrr": 0.0 if first is None else 1.0 / first,
        "ndcg": 0.0 if ideal == 0 else dcg / ideal,
    }


def run_query(search_fn: Callable[[str], dict[str, Any]], item: dict[str, Any]) -> dict[str, Any]:
    timings = []
    output: dict[str, Any] = {"candidates": []}
    for _ in range(QUERY_REPEATS):
        started = time.perf_counter()
        output = search_fn(item["query"])
        timings.append((time.perf_counter() - started) * 1000)
    candidates = output.get("candidates", [])
    paths = []
    scores = []
    seen_paths = set()
    for candidate in candidates:
        path = canonical_path(candidate.get("path", ""))
        if not path or path in seen_paths:
            continue
        seen_paths.add(path)
        paths.append(path)
        scores.append(candidate.get("score"))
        if len(paths) >= TOP_K:
            break
    metrics = ranked_metrics(paths, item["relevant_paths"])
    return {
        **item,
        **metrics,
        "candidate_paths": paths,
        "candidate_scores": scores,
        "latency_ms": statistics.median(timings),
        "latency_p95_ms": sorted(timings)[max(0, math.ceil(0.95 * len(timings)) - 1)],
        "false_positive": bool(paths) if not item["relevant_paths"] else False,
    }


def percentile(values: list[float], p: float) -> float:
    values = sorted(values)
    return values[max(0, min(len(values) - 1, math.ceil(p * len(values)) - 1))]


def bootstrap_ci(rows: list[dict[str, Any]], field: str) -> list[float]:
    if not rows:
        return [0.0, 0.0]
    rng = random.Random(SEED + sum(ord(char) for char in field))
    values = []
    for _ in range(BOOTSTRAP_RUNS):
        sample = [rows[rng.randrange(len(rows))] for _ in rows]
        values.append(statistics.mean(float(row[field]) for row in sample))
    return [percentile(values, 0.025), percentile(values, 0.975)]


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    answerable = [row for row in rows if row["relevant_paths"]]
    no_answer = [row for row in rows if not row["relevant_paths"]]
    result: dict[str, Any] = {}
    for field in ("ndcg", "recall", "hit", "mrr"):
        result[field] = statistics.mean(float(row[field]) for row in answerable)
        result[f"{field}_ci"] = bootstrap_ci(answerable, field)
    result["false_positive_rate"] = (
        statistics.mean(float(row["false_positive"]) for row in no_answer) if no_answer else 0.0
    )
    result["latency_p50_ms"] = statistics.median(row["latency_ms"] for row in rows)
    result["latency_p95_ms"] = percentile([row["latency_ms"] for row in rows], 0.95)
    return result


def paired_delta(rows_a: list[dict[str, Any]], rows_b: list[dict[str, Any]], field: str) -> dict[str, Any]:
    by_id_a = {row["id"]: row for row in rows_a if row["relevant_paths"]}
    pairs = [(by_id_a[row["id"]], row) for row in rows_b if row["id"] in by_id_a and row["relevant_paths"]]
    observed = statistics.mean(float(b[field]) - float(a[field]) for a, b in pairs)
    rng = random.Random(SEED + 991)
    samples = []
    for _ in range(BOOTSTRAP_RUNS):
        sample = [pairs[rng.randrange(len(pairs))] for _ in pairs]
        samples.append(statistics.mean(float(b[field]) - float(a[field]) for a, b in sample))
    return {"delta": observed, "ci": [percentile(samples, 0.025), percentile(samples, 0.975)]}


def esc(value: Any) -> str:
    return html.escape(str(value))


def forest_svg(summary: dict[str, Any]) -> str:
    width, height = 860, 300
    left, right, top, row_h = 210, 80, 38, 48
    plot_w = width - left - right
    ticks = [0, .2, .4, .6, .8, 1]
    parts = [
        f'<svg class="chart" viewBox="0 0 {width} {height}" role="img" aria-labelledby="forest-title forest-desc">',
        '<title id="forest-title">Overall nDCG at 10 with bootstrap confidence intervals</title>',
        '<desc id="forest-desc">Five retrieval stages compared on 72 answerable queries.</desc>',
    ]
    for tick in ticks:
        x = left + tick * plot_w
        parts.append(f'<line class="grid" x1="{x:.1f}" x2="{x:.1f}" y1="20" y2="258"/>')
        parts.append(f'<text class="axis" x="{x:.1f}" y="282" text-anchor="middle">{tick:.1f}</text>')
    for index, stage in enumerate(STAGES):
        y = top + index * row_h
        metric = summary[stage]
        low, high = metric["ndcg_ci"]
        value = metric["ndcg"]
        x1, x2, x = left + low * plot_w, left + high * plot_w, left + value * plot_w
        parts.append(f'<text x="{left - 14}" y="{y + 5}" text-anchor="end">{esc(STAGE_LABELS[stage])}</text>')
        parts.append(f'<line class="ci" x1="{x1:.1f}" x2="{x2:.1f}" y1="{y}" y2="{y}"/>')
        parts.append(f'<line class="ci-cap" x1="{x1:.1f}" x2="{x1:.1f}" y1="{y-6}" y2="{y+6}"/>')
        parts.append(f'<line class="ci-cap" x1="{x2:.1f}" x2="{x2:.1f}" y1="{y-6}" y2="{y+6}"/>')
        parts.append(f'<circle cx="{x:.1f}" cy="{y}" r="6" fill="{COLORS[stage]}"/>')
        parts.append(f'<text class="value" x="{min(width-42, x+10):.1f}" y="{y+5}">{value:.3f}</text>')
    parts.append(f'<text class="axis-title" x="{left + plot_w/2:.1f}" y="298" text-anchor="middle">nDCG@10</text></svg>')
    return "".join(parts)


def family_svg(by_family: dict[str, dict[str, Any]]) -> str:
    families = ("entity_exact", "entity_context", "relation")
    width, height = 900, 390
    left, right, top, group_h = 180, 70, 42, 104
    plot_w = width - left - right
    parts = [
        f'<svg class="chart" viewBox="0 0 {width} {height}" role="img" aria-labelledby="family-title family-desc">',
        '<title id="family-title">nDCG at 10 by query family</title>',
        '<desc id="family-desc">Small multiple dot plot comparing five stages across three answerable query families.</desc>',
    ]
    for tick in (0, .25, .5, .75, 1):
        x = left + tick * plot_w
        parts.append(f'<line class="grid" x1="{x:.1f}" x2="{x:.1f}" y1="18" y2="340"/>')
        parts.append(f'<text class="axis" x="{x:.1f}" y="366" text-anchor="middle">{tick:.2f}</text>')
    labels = {"entity_exact": "Exact entity", "entity_context": "Entity context", "relation": "Relation"}
    for family_index, family in enumerate(families):
        base_y = top + family_index * group_h
        parts.append(f'<text class="family-label" x="{left-18}" y="{base_y+40}" text-anchor="end">{labels[family]}</text>')
        for stage_index, stage in enumerate(STAGES):
            y = base_y + stage_index * 16
            value = by_family[family][stage]["ndcg"]
            x = left + value * plot_w
            parts.append(f'<circle cx="{x:.1f}" cy="{y}" r="4.5" fill="{COLORS[stage]}"><title>{esc(STAGE_LABELS[stage])}: {value:.3f}</title></circle>')
            if family_index == 0:
                parts.append(f'<text class="series-label" x="{x+8:.1f}" y="{y+4}">{esc(stage)}</text>')
    parts.append(f'<text class="axis-title" x="{left + plot_w/2:.1f}" y="386" text-anchor="middle">nDCG@10</text></svg>')
    return "".join(parts)


def delta_svg(deltas: dict[str, dict[str, Any]]) -> str:
    labels = (("G1-G0", "Enrichment: G1 - G0"), ("H1-H0", "Enrichment: H1 - H0"),
              ("H1-L1", "Hybrid safety: H1 - L1"), ("H1-G1", "Fusion effect: H1 - G1"))
    width, height = 860, 260
    left, right, top, row_h, bound = 240, 90, 38, 48, .5
    plot_w = width - left - right
    x_of = lambda value: left + ((value + bound) / (2 * bound)) * plot_w
    parts = [
        f'<svg class="chart" viewBox="0 0 {width} {height}" role="img" aria-labelledby="delta-title delta-desc">',
        '<title id="delta-title">Paired nDCG differences</title>',
        '<desc id="delta-desc">Paired bootstrap differences with 95 percent confidence intervals.</desc>',
    ]
    for tick in (-.5, -.25, 0, .25, .5):
        x = x_of(tick)
        parts.append(f'<line class="{"zero" if tick == 0 else "grid"}" x1="{x:.1f}" x2="{x:.1f}" y1="18" y2="212"/>')
        parts.append(f'<text class="axis" x="{x:.1f}" y="238" text-anchor="middle">{tick:+.2f}</text>')
    for index, (key, label) in enumerate(labels):
        y = top + index * row_h
        item = deltas[key]
        low, high = item["ci"]
        value = item["delta"]
        parts.append(f'<text x="{left-14}" y="{y+5}" text-anchor="end">{label}</text>')
        parts.append(f'<line class="ci" x1="{x_of(max(-bound,low)):.1f}" x2="{x_of(min(bound,high)):.1f}" y1="{y}" y2="{y}"/>')
        parts.append(f'<circle cx="{x_of(max(-bound,min(bound,value))):.1f}" cy="{y}" r="6" fill="{COLORS["H1" if key.startswith("H1") else "G1"]}"/>')
        parts.append(f'<text class="value" x="{x_of(max(-bound,min(bound,value)))+10:.1f}" y="{y+5}">{value:+.3f}</text>')
    parts.append('</svg>')
    return "".join(parts)


def latency_svg(summary: dict[str, Any]) -> str:
    width, height = 860, 290
    left, right, top, row_h = 210, 90, 38, 46
    values = [summary[stage]["latency_p95_ms"] for stage in STAGES]
    max_value = max(values) * 1.15 or 1
    plot_w = width - left - right
    parts = [
        f'<svg class="chart" viewBox="0 0 {width} {height}" role="img" aria-labelledby="lat-title lat-desc">',
        '<title id="lat-title">Warm query latency</title>',
        '<desc id="lat-desc">Median and 95th percentile latency in milliseconds for each retrieval stage.</desc>',
    ]
    for tick in (0, .25, .5, .75, 1):
        x = left + tick * plot_w
        parts.append(f'<line class="grid" x1="{x:.1f}" x2="{x:.1f}" y1="18" y2="240"/>')
        parts.append(f'<text class="axis" x="{x:.1f}" y="266" text-anchor="middle">{tick*max_value:.1f}</text>')
    for index, stage in enumerate(STAGES):
        y = top + index * row_h
        p50 = summary[stage]["latency_p50_ms"]
        p95 = summary[stage]["latency_p95_ms"]
        x50, x95 = left + p50/max_value*plot_w, left + p95/max_value*plot_w
        parts.append(f'<text x="{left-14}" y="{y+5}" text-anchor="end">{esc(STAGE_LABELS[stage])}</text>')
        parts.append(f'<line class="ci" x1="{x50:.1f}" x2="{x95:.1f}" y1="{y}" y2="{y}"/>')
        parts.append(f'<circle cx="{x50:.1f}" cy="{y}" r="5" fill="{COLORS[stage]}"/>')
        parts.append(f'<path d="M{x95-5:.1f},{y-5} L{x95+5:.1f},{y+5} M{x95+5:.1f},{y-5} L{x95-5:.1f},{y+5}" stroke="{COLORS[stage]}" stroke-width="2"/>')
        parts.append(f'<text class="value" x="{x95+9:.1f}" y="{y+5}">{p50:.2f}/{p95:.2f}</text>')
    parts.append(f'<text class="axis-title" x="{left+plot_w/2:.1f}" y="286" text-anchor="middle">Latency (ms), dot=P50, cross=P95</text></svg>')
    return "".join(parts)


def report_html(manifest: dict[str, Any]) -> str:
    summary = manifest["summary"]
    by_family = manifest["by_family"]
    rows = "".join(
        f"<tr><td>{esc(STAGE_LABELS[stage])}</td><td>{summary[stage]['ndcg']:.3f}</td>"
        f"<td>{summary[stage]['recall']:.3f}</td><td>{summary[stage]['hit']:.3f}</td>"
        f"<td>{summary[stage]['mrr']:.3f}</td><td>{summary[stage]['false_positive_rate']:.3f}</td>"
        f"<td>{summary[stage]['latency_p50_ms']:.2f}</td><td>{summary[stage]['latency_p95_ms']:.2f}</td></tr>"
        for stage in STAGES
    )
    health = manifest["graph_health"]
    conclusion = (
        f"Enrichment changes Graph nDCG@10 by {manifest['deltas']['G1-G0']['delta']:+.3f} "
        f"and hybrid by {manifest['deltas']['H1-H0']['delta']:+.3f}. "
        f"The H1-L1 paired difference is {manifest['deltas']['H1-L1']['delta']:+.3f}; "
        "confidence intervals and family breakdowns below define the valid scope of that result."
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Mneme Graph Enrichment Benchmark</title>
<style>
:root{{--bg:#fbfcfd;--fg:#17202a;--muted:#5d6874;--rule:#d7dde3;--soft:#edf1f4;--accent:#245a8d}}
@media(prefers-color-scheme:dark){{:root{{--bg:#12171c;--fg:#e8edf2;--muted:#aeb7c0;--rule:#39434d;--soft:#202830;--accent:#76a9d5}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--fg);font-family:Inter,ui-sans-serif,system-ui,-apple-system,sans-serif;letter-spacing:0;line-height:1.55}}
main{{max-width:1120px;margin:0 auto;padding:48px 28px 80px}}h1{{font-size:34px;font-weight:500;margin:0 0 8px}}h2{{font-size:21px;font-weight:500;margin:44px 0 12px;border-bottom:1px solid var(--rule);padding-bottom:8px}}p{{max-width:86ch}}.meta,.caption{{color:var(--muted);font-size:13px}}.lede{{font-size:18px;max-width:84ch}}.finding{{border-left:4px solid var(--accent);padding:8px 0 8px 18px;margin:24px 0;font-size:17px}}.chart{{display:block;width:100%;height:auto;max-height:430px;margin:12px 0 4px;overflow:visible}}.chart text{{fill:var(--fg);font-size:13px;font-weight:400}}.chart .axis,.chart .series-label{{fill:var(--muted);font-size:12px}}.chart .axis-title,.chart .family-label{{font-weight:500}}.chart .grid{{stroke:var(--rule);stroke-width:1}}.chart .zero{{stroke:var(--fg);stroke-width:1.5}}.chart .ci,.chart .ci-cap{{stroke:var(--fg);stroke-width:1.5}}.chart .value{{font-variant-numeric:tabular-nums;font-weight:500}}table{{width:100%;border-collapse:collapse;font-size:13px;font-variant-numeric:tabular-nums}}th,td{{text-align:right;padding:9px 10px;border-bottom:1px solid var(--rule)}}th:first-child,td:first-child{{text-align:left}}th{{font-weight:500;color:var(--muted)}}code{{background:var(--soft);padding:2px 5px;border-radius:3px}}.methods{{columns:2;column-gap:36px}}.methods p{{break-inside:avoid;margin-top:0}}@media(max-width:700px){{main{{padding:28px 16px 60px}}h1{{font-size:27px}}.methods{{columns:1}}.table-wrap{{overflow-x:auto}}}}
</style></head><body><main>
<p class="meta">Mneme Research · Frozen diagnostic benchmark · {esc(manifest['created_at'])}</p>
<h1>Graph enrichment retrieval benchmark</h1>
<p class="lede">A controlled ablation of deterministic Graph, agent enrichment, and global FTS5 fusion on one 142-page Markdown bundle. The benchmark contains 72 construction-aware answerable queries and 8 synthetic no-answer controls.</p>
<p class="finding">{esc(conclusion)}</p>
<h2>Overall retrieval quality</h2>{forest_svg(summary)}
<p class="caption">Points are mean binary nDCG@10; horizontal lines are query-bootstrap 95% confidence intervals (10,000 resamples). No-answer controls are excluded from ranking metrics.</p>
<h2>Query-family response</h2>{family_svg(by_family)}
<p class="caption">The family split is essential: entity and relation qrels are derived from the frozen extraction manifest and measure mechanism coverage, not independent general-search quality.</p>
<h2>Paired effects</h2>{delta_svg(manifest['deltas'])}
<p class="caption">Positive values favor the second system. Intervals crossing zero do not establish a stable directional effect on this diagnostic set.</p>
<h2>Latency</h2>{latency_svg(summary)}
<p class="caption">Warm in-process measurements; each query is repeated {QUERY_REPEATS} times. They describe this local machine and are not service-level benchmarks.</p>
<h2>Metric table</h2><div class="table-wrap"><table><thead><tr><th>Stage</th><th>nDCG@10</th><th>Macro Recall@10</th><th>Hit@10</th><th>MRR@10</th><th>No-answer FPR</th><th>P50 ms</th><th>P95 ms</th></tr></thead><tbody>{rows}</tbody></table></div>
<h2>Graph construction</h2><div class="table-wrap"><table><thead><tr><th>Graph</th><th>Entities</th><th>Relations</th><th>LLM entities</th><th>LLM relations</th><th>Components</th><th>Orphans</th></tr></thead><tbody>
<tr><td>G0 deterministic</td><td>{health['G0']['entity_count']}</td><td>{health['G0']['relation_count']}</td><td>{health['G0']['llm_entity_count']}</td><td>{health['G0']['llm_relation_count']}</td><td>{health['G0']['connected_component_count']}</td><td>{health['G0']['orphan_entity_count']}</td></tr>
<tr><td>G1 enriched</td><td>{health['G1']['entity_count']}</td><td>{health['G1']['relation_count']}</td><td>{health['G1']['llm_entity_count']}</td><td>{health['G1']['llm_relation_count']}</td><td>{health['G1']['connected_component_count']}</td><td>{health['G1']['orphan_entity_count']}</td></tr></tbody></table></div>
<h2>Methods and limits</h2><div class="methods"><p><strong>Corpus.</strong> One private 142-page Feishu Markdown export. Export pairs with identical bodies (<code>foo.md</code>/<code>foo--2.md</code>) are treated as one document equivalence class in qrels and ranked candidates.</p><p><strong>Metrics.</strong> nDCG uses binary relevance and logarithmic rank discount. Recall is macro-averaged per answerable query; Hit records any relevant top-10 result; MRR uses the first relevant top-10 rank. No-answer controls are excluded and reported as FPR.</p><p><strong>Systems.</strong> L1 is global FTS5. G0 derives only pages, tags, and Markdown links. G1 adds the frozen agent extraction manifest. H0/H1 use the production Graph + global FTS union.</p><p><strong>Labels.</strong> Entity, context, and relation qrels are deterministically sampled from the extraction manifest. They are suitable for enrichment ablation, but share construction provenance with G1 and must not be treated as independent human relevance judgments.</p><p><strong>Known boundary.</strong> This report does not compare L2, answer synthesis, citation correctness, or independent user questions. A separate double-annotated benchmark is required for those claims.</p></div>
<p class="meta">Code <code>{esc(manifest['code_revision'][:12])}</code> · Mneme {esc(manifest['mneme_version'])} · qrels SHA-256 <code>{esc(manifest['qrels_sha256'][:16])}</code> · extraction SHA-256 <code>{esc(manifest['extraction_sha256'][:16])}</code></p>
</main></body></html>"""


def run(bundle: Path, extraction: Path, qrels_path: Path, out: Path) -> None:
    qrels = read_qrels(qrels_path)
    if len(qrels) != 80:
        raise ValueError(f"expected 80 frozen qrels, got {len(qrels)}")
    out.mkdir(parents=True, exist_ok=True)
    extraction_payload = load_extractions(extraction)

    with tempfile.TemporaryDirectory(prefix="mneme-graph-benchmark-") as temp_dir:
        temp_bundle = Path(temp_dir) / "wiki"
        shutil.copytree(bundle, temp_bundle, ignore=shutil.ignore_patterns(".mneme"))

        started = time.perf_counter()
        indexlib.reindex_paths(indexable_paths(temp_bundle), temp_bundle)
        fts_build_ms = (time.perf_counter() - started) * 1000

        started = time.perf_counter()
        graphlib.rebuild_graph(temp_bundle)
        g0_build_ms = (time.perf_counter() - started) * 1000
        g0_health = graphlib.graph_health(graphlib.graph_index_path(temp_bundle))

        fts_db = indexlib.fts_index_path(temp_bundle)
        graph_db = graphlib.graph_index_path(temp_bundle)
        stage_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)

        searchers: dict[str, Callable[[str], dict[str, Any]]] = {
            "L1": lambda query: indexlib.search(query, fts_db, k=TOP_K),
            "G0": lambda query: graphlib.search_graph(graph_db, query, k=TOP_K),
            "H0": lambda query: indexlib.search_hybrid(temp_bundle, query, k=TOP_K),
        }
        for stage in ("L1", "G0", "H0"):
            for item in qrels:
                stage_rows[stage].append({"stage": stage, **run_query(searchers[stage], item)})

        started = time.perf_counter()
        graphlib.ingest_extraction(graph_db, extraction_payload, persist=False)
        enrichment_ms = (time.perf_counter() - started) * 1000
        g1_health = graphlib.graph_health(graph_db)
        searchers = {
            "G1": lambda query: graphlib.search_graph(graph_db, query, k=TOP_K),
            "H1": lambda query: indexlib.search_hybrid(temp_bundle, query, k=TOP_K),
        }
        for stage in ("G1", "H1"):
            for item in qrels:
                stage_rows[stage].append({"stage": stage, **run_query(searchers[stage], item)})

    summary = {stage: summarize(stage_rows[stage]) for stage in STAGES}
    families = ("entity_exact", "entity_context", "relation")
    by_family = {
        family: {
            stage: summarize([row for row in stage_rows[stage] if row["category"] == family])
            for stage in STAGES
        }
        for family in families
    }
    deltas = {
        "G1-G0": paired_delta(stage_rows["G0"], stage_rows["G1"], "ndcg"),
        "H1-H0": paired_delta(stage_rows["H0"], stage_rows["H1"], "ndcg"),
        "H1-L1": paired_delta(stage_rows["L1"], stage_rows["H1"], "ndcg"),
        "H1-G1": paired_delta(stage_rows["G1"], stage_rows["H1"], "ndcg"),
    }
    manifest = {
        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "design": "construction-aware Graph enrichment diagnostic",
        "mneme_version": __version__,
        "code_revision": git_revision(),
        "python": sys.version,
        "platform": platform.platform(),
        "bundle_page_count": len(indexable_paths(bundle)),
        "bundle_path_not_published": True,
        "qrels_count": len(qrels),
        "qrels_sha256": sha256_file(qrels_path),
        "extraction_sha256": sha256_file(extraction),
        "runner_sha256": sha256_file(Path(__file__)),
        "top_k": TOP_K,
        "query_repeats": QUERY_REPEATS,
        "bootstrap_runs": BOOTSTRAP_RUNS,
        "seed": SEED,
        "build_ms": {"FTS5": fts_build_ms, "G0": g0_build_ms, "enrichment": enrichment_ms},
        "graph_health": {"G0": g0_health, "G1": g1_health},
        "summary": summary,
        "by_family": by_family,
        "deltas": deltas,
    }

    stem = out / "graph-enrichment-benchmark"
    stem.with_suffix(".manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    with stem.with_suffix(".results.jsonl").open("w", encoding="utf-8") as handle:
        for stage in STAGES:
            for row in stage_rows[stage]:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    stem.with_suffix(".html").write_text(report_html(manifest), encoding="utf-8")
    print(stem.with_suffix(".html"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--extraction", type=Path, required=True)
    parser.add_argument(
        "--qrels", type=Path,
        default=ROOT / "reports" / "experiments" / "graph-enrichment-benchmark.qrels.jsonl",
    )
    parser.add_argument("--out", type=Path, default=ROOT / "reports" / "experiments")
    parser.add_argument("--prepare-qrels", action="store_true")
    args = parser.parse_args()
    if args.prepare_qrels:
        write_qrels(args.qrels, build_qrels(args.extraction))
        print(args.qrels)
        return
    run(args.bundle, args.extraction, args.qrels, args.out)


if __name__ == "__main__":
    main()
