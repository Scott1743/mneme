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
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]
SKILL_SCRIPTS = ROOT / "skills" / "mneme" / "scripts"
sys.path.insert(0, str(SKILL_SCRIPTS))

from mneme import __version__, graphlib, indexlib, okflib  # noqa: E402

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
CORPORA = ("base", "expanded")
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


def add_event_corpus(
    archive: Path,
    bundle: Path,
    qrels: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Copy Markdown event pages from a zip into an isolated benchmark bundle."""
    destination = bundle / "events"
    destination.mkdir(exist_ok=True)
    members: list[zipfile.ZipInfo] = []
    with zipfile.ZipFile(archive) as handle:
        for member in handle.infolist():
            parts = Path(member.filename).parts
            if member.is_dir() or not member.filename.endswith(".md"):
                continue
            if not parts or parts[0] != "events" or len(parts) != 2:
                continue
            if any(part in {"", ".", ".."} for part in parts):
                raise ValueError(f"unsafe event archive member: {member.filename}")
            members.append(member)
        if not members:
            raise ValueError("event archive contains no events/*.md pages")
        for member in sorted(members, key=lambda item: item.filename):
            target = destination / Path(member.filename).name
            target.write_bytes(handle.read(member))

    event_paths = list(destination.glob("*.md"))
    bodies = [sha256_file(path) for path in event_paths]
    raw_texts = [path.read_text(encoding="utf-8") for path in event_paths]
    texts = [text.casefold() for text in raw_texts]
    metadata = [okflib.parse_frontmatter(text) for text in raw_texts]
    metadata = [parsed[0] for parsed in metadata if parsed is not None]
    tag_counts = Counter(
        str(tag) for meta in metadata for tag in meta.get("tags", [])
    )
    event_dates = sorted(
        str(meta["event_date"]) for meta in metadata if meta.get("event_date")
    )
    overlaps = [
        item["id"] for item in (qrels or [])
        if item["relevant_paths"] and any(str(item["query"]).casefold() in text for text in texts)
    ]
    return {
        "page_count": len(members),
        "unique_body_count": len(set(bodies)),
        "archive_sha256": sha256_file(archive),
        "archive_name": archive.name,
        "exact_query_overlap_ids": overlaps,
        "frontmatter_count": len(metadata),
        "event_date_range": [event_dates[0], event_dates[-1]] if event_dates else [],
        "top_tags": tag_counts.most_common(8),
    }


def ranked_metrics(paths: list[str], relevant_paths: list[str]) -> dict[str, float | int | None]:
    relevant = set(relevant_paths)
    if not relevant:
        return {
            "rank": None, "accuracy": 0.0, "precision": 0.0,
            "recall": 0.0, "f1": 0.0, "hit": 0.0, "mrr": 0.0, "ndcg": 0.0,
        }
    ranks = [index for index, path in enumerate(paths[:TOP_K], 1) if path in relevant]
    first = min(ranks) if ranks else None
    precision = len(ranks) / TOP_K
    recall = len(ranks) / len(relevant)
    f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
    dcg = sum(1.0 / math.log2(rank + 1) for rank in ranks)
    ideal = sum(1.0 / math.log2(rank + 1) for rank in range(1, min(len(relevant), TOP_K) + 1))
    return {
        "rank": first,
        "accuracy": float(first == 1),
        "precision": precision,
        "hit": float(bool(ranks)),
        "recall": recall,
        "f1": f1,
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
    for field in ("ndcg", "accuracy", "precision", "recall", "f1", "hit", "mrr"):
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


def classic_metrics_svg(summary: dict[str, Any]) -> str:
    metrics = (
        ("accuracy", "Top-1 accuracy", "#3573b8", "circle"),
        ("precision", "Precision@10", "#238b68", "square"),
        ("recall", "Macro Recall@10", "#c87a18", "diamond"),
        ("f1", "Macro F1@10", "#a44a8b", "cross"),
    )
    width, height = 900, 330
    left, right, top, row_h = 200, 70, 52, 47
    plot_w = width - left - right
    parts = [
        f'<svg class="chart" viewBox="0 0 {width} {height}" role="img" aria-labelledby="classic-title classic-desc">',
        '<title id="classic-title">Classic retrieval metric profile</title>',
        '<desc id="classic-desc">Top-1 accuracy, precision at 10, macro recall at 10, and macro F1 at 10 for five retrieval stages.</desc>',
    ]
    for tick in (0, .2, .4, .6, .8, 1):
        x = left + tick * plot_w
        parts.append(f'<line class="grid" x1="{x:.1f}" x2="{x:.1f}" y1="38" y2="270"/>')
        parts.append(f'<text class="axis" x="{x:.1f}" y="298" text-anchor="middle">{tick:.1f}</text>')
    for index, stage in enumerate(STAGES):
        y = top + index * row_h
        parts.append(f'<text x="{left-14}" y="{y+5}" text-anchor="end">{esc(STAGE_LABELS[stage])}</text>')
        for metric_index, (key, label, color, shape) in enumerate(metrics):
            value = summary[stage][key]
            x = left + value * plot_w
            offset = (metric_index - 1.5) * 8
            cy = y + offset
            title = f'{label}: {value:.3f}'
            if shape == "circle":
                parts.append(f'<circle cx="{x:.1f}" cy="{cy:.1f}" r="4.5" fill="{color}"><title>{title}</title></circle>')
            elif shape == "square":
                parts.append(f'<rect x="{x-4:.1f}" y="{cy-4:.1f}" width="8" height="8" fill="{color}"><title>{title}</title></rect>')
            elif shape == "diamond":
                parts.append(f'<path d="M{x:.1f},{cy-5:.1f} L{x+5:.1f},{cy:.1f} L{x:.1f},{cy+5:.1f} L{x-5:.1f},{cy:.1f} Z" fill="{color}"><title>{title}</title></path>')
            else:
                parts.append(f'<path d="M{x-4:.1f},{cy-4:.1f} L{x+4:.1f},{cy+4:.1f} M{x+4:.1f},{cy-4:.1f} L{x-4:.1f},{cy+4:.1f}" stroke="{color}" stroke-width="2"><title>{title}</title></path>')
    legend_x = left
    for index, (_, label, color, _) in enumerate(metrics):
        x = legend_x + index * 155
        parts.append(f'<circle cx="{x:.1f}" cy="20" r="4" fill="{color}"/><text class="axis" x="{x+9:.1f}" y="24">{label}</text>')
    parts.append(f'<text class="axis-title" x="{left+plot_w/2:.1f}" y="325" text-anchor="middle">Score</text></svg>')
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


def corpus_expansion_svg(base: dict[str, Any], expanded: dict[str, Any]) -> str:
    width, height = 900, 330
    left, right, top, row_h = 210, 90, 45, 50
    plot_w = width - left - right
    parts = [
        f'<svg class="chart" viewBox="0 0 {width} {height}" role="img" aria-labelledby="growth-title growth-desc">',
        '<title id="growth-title">Frozen-target nDCG before and after event corpus expansion</title>',
        '<desc id="growth-desc">Paired points compare the 142-page base corpus with the 219-page corpus after adding 77 topical event pages.</desc>',
    ]
    for tick in (0, .2, .4, .6, .8, 1):
        x = left + tick * plot_w
        parts.append(f'<line class="grid" x1="{x:.1f}" x2="{x:.1f}" y1="24" y2="276"/>')
        parts.append(f'<text class="axis" x="{x:.1f}" y="302" text-anchor="middle">{tick:.1f}</text>')
    for index, stage in enumerate(STAGES):
        y = top + index * row_h
        before = base[stage]["ndcg"]
        after = expanded[stage]["ndcg"]
        x1, x2 = left + before * plot_w, left + after * plot_w
        parts.append(f'<text x="{left-14}" y="{y+5}" text-anchor="end">{esc(STAGE_LABELS[stage])}</text>')
        parts.append(f'<line class="ci" x1="{x1:.1f}" x2="{x2:.1f}" y1="{y}" y2="{y}"/>')
        parts.append(f'<circle cx="{x1:.1f}" cy="{y}" r="5" fill="{COLORS[stage]}"><title>Base: {before:.3f}</title></circle>')
        parts.append(f'<rect x="{x2-5:.1f}" y="{y-5}" width="10" height="10" fill="{COLORS[stage]}"><title>Expanded: {after:.3f}</title></rect>')
        anchor = min(width - 48, max(x1, x2) + 10)
        parts.append(f'<text class="value" x="{anchor:.1f}" y="{y+5}">{after-before:+.3f}</text>')
    parts.append(f'<text class="axis-title" x="{left+plot_w/2:.1f}" y="326" text-anchor="middle">Frozen-target nDCG@10 · circle=base, square=expanded</text></svg>')
    return "".join(parts)


def corpus_statement_html(manifest: dict[str, Any]) -> str:
    events = manifest["event_corpus"]
    date_range = " to ".join(events["event_date_range"]) or "not declared"
    tags = ", ".join(f"{tag} ({count})" for tag, count in events["top_tags"])
    return (
        "<p>The relevance labels and the retrieval corpus do not have the same scope. "
        "All 80 qrels belong to the base corpus; the event cohort is an unjudged, topical "
        "stress addition and is never treated as a labeled negative set.</p>"
        '<div class="table-wrap"><table class="question-table"><thead><tr>'
        "<th>Partition</th><th>Content pages</th><th>Graph treatment</th><th>Evaluation role</th>"
        "</tr></thead><tbody>"
        f"<tr><td>Base Feishu corpus</td><td>{manifest['base_page_count']}</td>"
        "<td>Deterministic + frozen enrichment</td><td>80 frozen qrels</td></tr>"
        f"<tr><td>Event cohort</td><td>{events['page_count']}</td>"
        "<td>Deterministic only</td><td>Unjudged topical stress documents</td></tr>"
        f"<tr><td>Expanded working corpus</td><td>{manifest['bundle_page_count']}</td>"
        "<td>Production hybrid ablation</td><td>Frozen-target retention</td></tr>"
        "</tbody></table></div>"
        f'<p class="caption">Event archive: <code>{esc(events["archive_name"])}</code>; '
        f'{events["unique_body_count"]} unique bodies; {events["frontmatter_count"]} pages with '
        f'frontmatter; event dates {esc(date_range)}. Most frequent tags: {esc(tags)}.</p>'
    )


def question_audit_html(qrels: list[dict[str, Any]]) -> str:
    labels = {
        "entity_exact": "Exact entity",
        "entity_context": "Entity context",
        "relation": "Relation",
        "no_answer": "No-answer control",
    }
    descriptions = {
        "entity_exact": "Extracted entity name; relevant pages explicitly mention it.",
        "entity_context": "Entity description with its name removed; tests contextual retrieval.",
        "relation": "Subject + predicate + object; relevant pages support that relation.",
        "no_answer": "Fixed synthetic token absent from the bundle; tests false positives.",
    }
    families = ("entity_exact", "entity_context", "relation", "no_answer")
    overview_rows, sample_rows, detail_sections = [], [], []
    for family in families:
        items = [item for item in qrels if item["category"] == family]
        overview_rows.append(
            f"<tr><td>{labels[family]}</td><td>{len(items)}</td><td>{descriptions[family]}</td></tr>"
        )
        for item in items[:4]:
            sample_rows.append(
                f'<tr><td>{esc(item["id"])}</td><td>{labels[family]}</td>'
                f'<td class="query-cell">{esc(item["query"])}</td>'
                f'<td>{len(item["relevant_paths"])}</td></tr>'
            )
        rows = "".join(
            f'<tr><td>{esc(item["id"])}</td><td class="query-cell">{esc(item["query"])}</td>'
            f'<td>{len(item["relevant_paths"])}</td><td>{esc(item["provenance"])}</td></tr>'
            for item in items
        )
        detail_sections.append(
            f'<details><summary>{labels[family]} · {len(items)} questions</summary>'
            f'<div class="table-wrap"><table class="question-table"><thead><tr>'
            f'<th>ID</th><th>Question</th><th>Relevant classes</th><th>Qrel source</th>'
            f'</tr></thead><tbody>{rows}</tbody></table></div></details>'
        )
    return (
        "<p>The questions were frozen on the base corpus before event expansion. Review their construction and examples before "
        "interpreting metrics; the first three families share provenance with the extraction manifest "
        "and measure enrichment coverage rather than independent human relevance.</p>"
        '<div class="table-wrap"><table class="question-table"><thead><tr><th>Family</th>'
        "<th>Count</th><th>Construction</th></tr></thead><tbody>"
        + "".join(overview_rows)
        + "</tbody></table></div><h3>Representative questions</h3>"
        '<div class="table-wrap"><table class="question-table"><thead><tr><th>ID</th>'
        "<th>Family</th><th>Question</th><th>Relevant classes</th></tr></thead><tbody>"
        + "".join(sample_rows)
        + "</tbody></table></div><h3>Full frozen question inventory</h3>"
        + "".join(detail_sections)
    )


def report_html(manifest: dict[str, Any], qrels: list[dict[str, Any]]) -> str:
    summary = manifest["summary"]
    base_summary = manifest["base_summary"]
    by_family = manifest["by_family"]
    rows = "".join(
        f"<tr><td>{esc(STAGE_LABELS[stage])}</td><td>{summary[stage]['ndcg']:.3f}</td>"
        f"<td>{summary[stage]['accuracy']:.3f}</td><td>{summary[stage]['precision']:.3f}</td>"
        f"<td>{summary[stage]['recall']:.3f}</td><td>{summary[stage]['f1']:.3f}</td><td>{summary[stage]['hit']:.3f}</td>"
        f"<td>{summary[stage]['mrr']:.3f}</td><td>{summary[stage]['false_positive_rate']:.3f}</td>"
        f"<td>{summary[stage]['latency_p50_ms']:.2f}</td><td>{summary[stage]['latency_p95_ms']:.2f}</td></tr>"
        for stage in STAGES
    )
    health = manifest["graph_health"]
    events = manifest["event_corpus"]
    fusion = manifest["deltas"]["H1-G1"]
    fusion_low, fusion_high = fusion["ci"]
    conclusion = (
        f"On the expanded corpus, G1 target nDCG@10 is {summary['G1']['ndcg']:.3f} and H1 is "
        f"{summary['H1']['ndcg']:.3f}, down {summary['H1']['ndcg']-base_summary['H1']['ndcg']:+.3f} "
        f"from base H1. The H1-G1 difference is {fusion['delta']:+.3f} "
        f"[{fusion_low:+.3f}, {fusion_high:+.3f}]; enrichment still improves H1 over H0 by "
        f"{manifest['deltas']['H1-H0']['delta']:+.3f}. These are frozen-target retention results, "
        "not exhaustive relevance judgments for the event cohort."
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Mneme Graph Enrichment Benchmark</title>
<style>
:root{{--bg:#fbfcfd;--fg:#17202a;--muted:#5d6874;--rule:#d7dde3;--soft:#edf1f4;--accent:#245a8d}}
@media(prefers-color-scheme:dark){{:root{{--bg:#12171c;--fg:#e8edf2;--muted:#aeb7c0;--rule:#39434d;--soft:#202830;--accent:#76a9d5}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--fg);font-family:Inter,ui-sans-serif,system-ui,-apple-system,sans-serif;letter-spacing:0;line-height:1.55}}
main{{max-width:1120px;margin:0 auto;padding:48px 28px 80px}}h1{{font-size:34px;font-weight:500;margin:0 0 8px}}h2{{font-size:21px;font-weight:500;margin:44px 0 12px;border-bottom:1px solid var(--rule);padding-bottom:8px}}h3{{font-size:16px;font-weight:500;margin:24px 0 8px}}p{{max-width:86ch}}.meta,.caption{{color:var(--muted);font-size:13px}}.lede{{font-size:18px;max-width:84ch}}.finding{{border-left:4px solid var(--accent);padding:8px 0 8px 18px;margin:24px 0;font-size:17px}}.chart{{display:block;width:100%;height:auto;max-height:430px;margin:12px 0 4px;overflow:visible}}.chart text{{fill:var(--fg);font-size:13px;font-weight:400}}.chart .axis,.chart .series-label{{fill:var(--muted);font-size:12px}}.chart .axis-title,.chart .family-label{{font-weight:500}}.chart .grid{{stroke:var(--rule);stroke-width:1}}.chart .zero{{stroke:var(--fg);stroke-width:1.5}}.chart .ci,.chart .ci-cap{{stroke:var(--fg);stroke-width:1.5}}.chart .value{{font-variant-numeric:tabular-nums;font-weight:500}}table{{width:100%;border-collapse:collapse;font-size:13px;font-variant-numeric:tabular-nums}}th,td{{text-align:right;padding:9px 10px;border-bottom:1px solid var(--rule)}}th:first-child,td:first-child{{text-align:left}}th{{font-weight:500;color:var(--muted)}}.question-table th,.question-table td{{text-align:left}}.query-cell{{min-width:320px}}details{{border-bottom:1px solid var(--rule);padding:10px 0}}summary{{cursor:pointer;font-weight:500}}code{{background:var(--soft);padding:2px 5px;border-radius:3px}}.methods{{columns:2;column-gap:36px}}.methods p{{break-inside:avoid;margin-top:0}}@media(max-width:700px){{main{{padding:28px 16px 60px}}h1{{font-size:27px}}.methods{{columns:1}}.table-wrap{{overflow-x:auto}}.query-cell{{min-width:240px}}}}
</style></head><body><main>
<p class="meta">Mneme Research · Frozen diagnostic benchmark · {esc(manifest['created_at'])}</p>
<h1>Graph enrichment retrieval benchmark</h1>
<p class="lede">A controlled ablation of deterministic Graph, agent enrichment, and global FTS5 fusion on a {manifest['bundle_page_count']}-page Markdown corpus. A paired stress condition adds {events['page_count']} topical AI event pages to the original {manifest['base_page_count']} pages; 72 construction-aware answerable queries and 8 synthetic no-answer controls remain frozen.</p>
<p class="finding">{esc(conclusion)}</p>
<h2>Corpus and label scope</h2>{corpus_statement_html(manifest)}
<h2>Benchmark questions</h2>{question_audit_html(qrels)}
<h2>Corpus expansion stress</h2>{corpus_expansion_svg(base_summary, summary)}
<p class="caption">The same frozen original targets are evaluated before and after adding the event cohort. Event pages were not exhaustively relevance-judged; the expanded score is therefore a target-retention diagnostic, not a complete relevance estimate. Exact query text occurs in the added cohort for {len(events['exact_query_overlap_ids'])} question(s): {esc(', '.join(events['exact_query_overlap_ids']) or 'none')}.</p>
<h2>Expanded-corpus target retrieval</h2>{forest_svg(summary)}
<p class="caption">Points are mean binary target nDCG@10 on the expanded corpus; horizontal lines are query-bootstrap 95% confidence intervals (10,000 resamples). No-answer controls are excluded.</p>
<h2>Classic metric profile</h2>{classic_metrics_svg(summary)}
<p class="caption">Precision@10 uses a fixed denominator of 10. Accuracy means whether rank 1 is a frozen target, not document-classification accuracy. Recall and F1 are macro-averaged over answerable base-corpus targets.</p>
<h2>Query-family response</h2>{family_svg(by_family)}
<p class="caption">The family split is essential: entity and relation qrels are derived from the frozen extraction manifest and measure mechanism coverage, not independent general-search quality.</p>
<h2>Paired effects</h2>{delta_svg(manifest['deltas'])}
<p class="caption">Positive values favor the second system. Intervals crossing zero do not establish a stable directional effect on this diagnostic set.</p>
<h2>Latency</h2>{latency_svg(summary)}
<p class="caption">Warm in-process measurements; each query is repeated {QUERY_REPEATS} times. They describe this local machine and are not service-level benchmarks.</p>
<h2>Expanded-corpus metric table</h2><div class="table-wrap"><table><thead><tr><th>Stage</th><th>Target nDCG@10</th><th>Top-1 target accuracy</th><th>Target Precision@10</th><th>Macro target Recall@10</th><th>Macro target F1@10</th><th>Target Hit@10</th><th>Target MRR@10</th><th>No-answer FPR</th><th>P50 ms</th><th>P95 ms</th></tr></thead><tbody>{rows}</tbody></table></div>
<h2>Graph construction</h2><div class="table-wrap"><table><thead><tr><th>Graph</th><th>Entities</th><th>Relations</th><th>LLM entities</th><th>LLM relations</th><th>Components</th><th>Orphans</th></tr></thead><tbody>
<tr><td>G0 deterministic</td><td>{health['G0']['entity_count']}</td><td>{health['G0']['relation_count']}</td><td>{health['G0']['llm_entity_count']}</td><td>{health['G0']['llm_relation_count']}</td><td>{health['G0']['connected_component_count']}</td><td>{health['G0']['orphan_entity_count']}</td></tr>
<tr><td>G1 enriched</td><td>{health['G1']['entity_count']}</td><td>{health['G1']['relation_count']}</td><td>{health['G1']['llm_entity_count']}</td><td>{health['G1']['llm_relation_count']}</td><td>{health['G1']['connected_component_count']}</td><td>{health['G1']['orphan_entity_count']}</td></tr></tbody></table></div>
<h2>Methods and limits</h2><div class="methods"><p><strong>Corpus.</strong> The base is one private {manifest['base_page_count']}-content-page Feishu Markdown export. The paired expansion adds {events['page_count']} unique event pages from <code>{esc(events['archive_name'])}</code>, producing {manifest['bundle_page_count']} content pages. FTS5 also indexes the reserved <code>index.md</code>/<code>log.md</code> files ({manifest['base_indexed_markdown_count']} and {manifest['indexed_markdown_count']} Markdown files respectively). Export pairs with identical bodies (<code>foo.md</code>/<code>foo--2.md</code>) are treated as one document equivalence class.</p><p><strong>Expansion labels.</strong> Qrels were frozen on the base corpus. Added event pages are topical stress documents, not judged negatives. Expanded-corpus metrics therefore ask whether the original relevant targets remain highly ranked; they cannot penalize or validate the relevance of new event hits.</p><p><strong>Metrics.</strong> nDCG uses binary target labels and logarithmic rank discount. Recall is macro-averaged per answerable query; Hit records any frozen target in the top 10; MRR uses the first frozen target rank. No-answer controls are excluded and reported as FPR.</p><p><strong>Systems.</strong> L1 is global FTS5. G0 derives only pages, tags, and Markdown links. G1 adds the frozen agent extraction manifest for the base corpus. H0/H1 use the production Graph + global FTS union. Event pages receive deterministic Graph indexing but no post-hoc enrichment.</p><p><strong>Labels.</strong> Entity, context, and relation qrels are deterministically sampled from the extraction manifest. They are suitable for enrichment ablation, but share construction provenance with G1 and must not be treated as independent human relevance judgments.</p><p><strong>Known boundary.</strong> This report does not compare L2, answer synthesis, citation correctness, or independent user questions. A separate double-annotated benchmark is required for those claims.</p></div>
<p class="meta">Code <code>{esc(manifest['code_revision'][:12])}</code> · Mneme {esc(manifest['mneme_version'])} · qrels SHA-256 <code>{esc(manifest['qrels_sha256'][:16])}</code> · events SHA-256 <code>{esc(events['archive_sha256'][:16])}</code> · extraction SHA-256 <code>{esc(manifest['extraction_sha256'][:16])}</code></p>
</main></body></html>"""


def run_corpus(
    temp_bundle: Path,
    extraction_payload: dict[str, Any],
    qrels: list[dict[str, Any]],
    corpus: str,
) -> dict[str, Any]:
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
            stage_rows[stage].append({
                "corpus": corpus, "stage": stage, **run_query(searchers[stage], item),
            })

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
            stage_rows[stage].append({
                "corpus": corpus, "stage": stage, **run_query(searchers[stage], item),
            })
    return {
        "rows": stage_rows,
        "summary": {stage: summarize(stage_rows[stage]) for stage in STAGES},
        "graph_health": {"G0": g0_health, "G1": g1_health},
        "build_ms": {"FTS5": fts_build_ms, "G0": g0_build_ms, "enrichment": enrichment_ms},
        "indexed_markdown_count": len(indexable_paths(temp_bundle)),
        "content_page_count": sum(
            path.name not in {"index.md", "log.md"} for path in indexable_paths(temp_bundle)
        ),
    }


def run(bundle: Path, extraction: Path, events_zip: Path, qrels_path: Path, out: Path) -> None:
    qrels = read_qrels(qrels_path)
    if len(qrels) != 80:
        raise ValueError(f"expected 80 frozen qrels, got {len(qrels)}")
    out.mkdir(parents=True, exist_ok=True)
    extraction_payload = load_extractions(extraction)

    corpus_runs: dict[str, dict[str, Any]] = {}
    event_audit: dict[str, Any] = {}
    with tempfile.TemporaryDirectory(prefix="mneme-graph-benchmark-") as temp_dir:
        for corpus in CORPORA:
            temp_bundle = Path(temp_dir) / corpus / "wiki"
            shutil.copytree(bundle, temp_bundle, ignore=shutil.ignore_patterns(".mneme"))
            if corpus == "expanded":
                event_audit = add_event_corpus(events_zip, temp_bundle, qrels)
            corpus_runs[corpus] = run_corpus(temp_bundle, extraction_payload, qrels, corpus)

    stage_rows = corpus_runs["expanded"]["rows"]
    summary = corpus_runs["expanded"]["summary"]
    base_summary = corpus_runs["base"]["summary"]
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
        "bundle_page_count": corpus_runs["expanded"]["content_page_count"],
        "base_page_count": corpus_runs["base"]["content_page_count"],
        "indexed_markdown_count": corpus_runs["expanded"]["indexed_markdown_count"],
        "base_indexed_markdown_count": corpus_runs["base"]["indexed_markdown_count"],
        "event_corpus": event_audit,
        "bundle_path_not_published": True,
        "qrels_count": len(qrels),
        "qrels_sha256": sha256_file(qrels_path),
        "extraction_sha256": sha256_file(extraction),
        "runner_sha256": sha256_file(Path(__file__)),
        "top_k": TOP_K,
        "query_repeats": QUERY_REPEATS,
        "bootstrap_runs": BOOTSTRAP_RUNS,
        "seed": SEED,
        "build_ms": {corpus: corpus_runs[corpus]["build_ms"] for corpus in CORPORA},
        "graph_health": corpus_runs["expanded"]["graph_health"],
        "base_graph_health": corpus_runs["base"]["graph_health"],
        "base_summary": base_summary,
        "summary": summary,
        "by_family": by_family,
        "deltas": deltas,
    }

    stem = out / "graph-enrichment-benchmark"
    stem.with_suffix(".manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    with stem.with_suffix(".results.jsonl").open("w", encoding="utf-8") as handle:
        for corpus in CORPORA:
            for stage in STAGES:
                for row in corpus_runs[corpus]["rows"][stage]:
                    handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    stem.with_suffix(".html").write_text(report_html(manifest, qrels), encoding="utf-8")
    print(stem.with_suffix(".html"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--extraction", type=Path, required=True)
    parser.add_argument(
        "--events-zip", type=Path,
        default=ROOT / "reports" / "events.zip",
        help="topical event corpus added for the paired expansion stress condition",
    )
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
    run(args.bundle, args.extraction, args.events_zip, args.qrels, args.out)


if __name__ == "__main__":
    main()
