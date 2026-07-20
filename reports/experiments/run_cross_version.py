#!/usr/bin/env python3
"""Cross-version retrieval regression on the five historical qrels.

Extends ``run_design01_historical.py`` with two v4.0 stages: ``G`` (graph-only)
and ``G+L1`` (Graph + FTS5 weighted hybrid via ``indexlib.search_hybrid``).

Scope limit: this is NOT the preregistered primary comparison. It replays only
five historical hand-selected qrels on the available private Feishu corpus
across four published versions (0.5 / 2.0 / 3.0 / 4.0). It has no
independently double-annotated 80-query set, no reranker, and no significance
claim. See ``reports/designs/2026-07-20-cross-version-comparison.md`` for the
full protocol.

The runner writes only aggregate corpus metadata, qrels, result paths, and
measurements to the repository. No source text leaves the private corpus.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import itertools
import json
import math
import os
import platform
import random
import statistics
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
SKILL_SCRIPTS = ROOT / "skills" / "mneme" / "scripts"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SKILL_SCRIPTS))
os.environ["PYTHONPATH"] = str(SKILL_SCRIPTS) + os.pathsep + os.environ.get("PYTHONPATH", "")

from mneme import __version__, indexlib, graphlib  # noqa: E402
from scripts.bootstrap_dogfood import bootstrap  # noqa: E402


# Historical 5-query regression set. Kept identical to
# run_design01_historical.py so L1/L2/L1+L2 numbers are directly comparable.
QRELS = (
    ("H01", "gstack", "AKMedL4gzoLwNwxg1cyc9bdxnPI"),
    ("H02", "Claude Code 工作流", "AKMedL4gzoLwNwxg1cyc9bdxnPI"),
    ("H03", "银行回单", "UCvpdz5z8oZqXTxCpD2cLAObnse"),
    ("H04", "录音", "Sic7dPX3aoxVByxxWqqcZAQunRb"),
    ("H05", "Hermes", "XVFudUEQeoXQjixSS9zckeNonAg"),
)
RRF_K = 60
TOP_K = 10
CANDIDATE_K = 50
INDEX_RUNS = 5
QUERY_REPEATS = 30
# v4.0 hybrid defaults (see indexlib.search_hybrid signature).
HYBRID_ALPHA = 0.4
HYBRID_BETA = 0.4
HYBRID_GAMMA = 0.2  # Inactive in Phase 1 (no entity embeddings).
GRAPH_DEPTH = 2


def percentile(values: list[float], p: float) -> float:
    values = sorted(values)
    return values[max(0, math.ceil(p * len(values)) - 1)] if values else 0.0


def corpus_digest(corpus: Path) -> dict[str, Any]:
    aggregate = hashlib.sha256()
    total_chars = 0
    files = sorted(corpus.glob("*.md"))
    for source in files:
        raw = source.read_bytes()
        aggregate.update(source.name.encode("utf-8"))
        aggregate.update(b"\0")
        aggregate.update(hashlib.sha256(raw).digest())
        total_chars += len(raw.decode("utf-8"))
    return {
        "label": "private Feishu Markdown export",
        "source_path_not_published": True,
        "source_files": len(files),
        "total_characters": total_chars,
        "aggregate_sha256": aggregate.hexdigest(),
    }


def paths_for_fts(bundle: Path) -> list[Path]:
    result = []
    for path in sorted(bundle.rglob("*.md")):
        if not path.is_file():
            continue
        parts = path.relative_to(bundle).parts
        if (
            ".mneme" not in parts
            and "sources" not in parts
            and "external-sources" not in parts
            and path.name not in {"index.md", "log.md"}
        ):
            result.append(path)
    return result


def git_revision() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dependency_lock() -> list[str]:
    return subprocess.run(
        [sys.executable, "-m", "pip", "freeze"], check=True, capture_output=True, text=True
    ).stdout.splitlines()


def dedupe_dense(hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pages: list[dict[str, Any]] = []
    seen: set[str] = set()
    for hit in hits:
        path = hit["path"]
        if path not in seen:
            pages.append({"path": path, "score": hit["distance"], "score_kind": "distance"})
            seen.add(path)
    return pages


def rrf(fts: list[dict[str, Any]], dense: list[dict[str, Any]]) -> list[dict[str, Any]]:
    scores: dict[str, float] = {}
    for items in (fts, dense):
        for rank, item in enumerate(items, start=1):
            scores[item["path"]] = scores.get(item["path"], 0.0) + 1.0 / (RRF_K + rank)
    return [
        {"path": path, "score": score, "score_kind": "rrf"}
        for path, score in sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:TOP_K]
    ]


def rank_of(items: list[dict[str, Any]], expected: str) -> int | None:
    return next((rank for rank, item in enumerate(items, start=1) if item["path"] == expected), None)


def metric_values(rows: list[dict[str, Any]]) -> dict[str, float]:
    ranks = [row["rank"] for row in rows]
    data: dict[str, float] = {}
    for cutoff in (1, 3, 5, 10):
        data[f"Recall@{cutoff}"] = sum(rank is not None and rank <= cutoff for rank in ranks) / len(ranks)
    data["MRR@10"] = statistics.mean(0.0 if rank is None else 1 / rank for rank in ranks)
    data["nDCG@10"] = statistics.mean(
        0.0 if rank is None else 1 / math.log2(rank + 1) for rank in ranks
    )
    return data


def bootstrap_ci(rows: list[dict[str, Any]], metric: Callable[[list[dict[str, Any]]], float]) -> tuple[float, float]:
    rng = random.Random(20260715)
    samples = [metric([rng.choice(rows) for _ in rows]) for _ in range(10_000)]
    return percentile(samples, 0.025), percentile(samples, 0.975)


def paired_randomization(a: list[dict[str, Any]], b: list[dict[str, Any]]) -> float:
    deltas = [
        (0.0 if right["rank"] is None else 1 / math.log2(right["rank"] + 1))
        - (0.0 if left["rank"] is None else 1 / math.log2(left["rank"] + 1))
        for left, right in zip(a, b)
    ]
    observed = abs(sum(deltas) / len(deltas))
    extreme = 0
    total = 0
    for signs in itertools.product((-1, 1), repeat=len(deltas)):
        total += 1
        if abs(sum(sign * delta for sign, delta in zip(signs, deltas)) / len(deltas)) >= observed:
            extreme += 1
    return extreme / total


def stage_rows(
    bundle: Path,
    embedder: indexlib.Embedder,
    graph_db: Path,
    fts_db: Path,
) -> dict[str, list[dict[str, Any]]]:
    """Run all six stages on the same bundle and return per-stage rows.

    Stages:
      L1     - FTS5 only (v2.0 default)
      L2     - pure semantic (v3.0 --l2)
      L1+L2  - RRF fusion (v3.x experiment script, rrf_k=60)
      G      - graph-only BFS (v4.0 --mode graph)
      G+L1   - Graph + FTS5 weighted hybrid (v4.0 --mode hybrid, CLI default)
      V0     - v0.5 historical baseline; placeholder, see notes
    """
    output: dict[str, list[dict[str, Any]]] = {
        "L1": [], "L2": [], "L1+L2": [], "G": [], "G+L1": [],
    }
    config_hash = hashlib.sha256(
        json.dumps(
            {
                "rrf_k": RRF_K,
                "top_k": TOP_K,
                "candidate_k": CANDIDATE_K,
                "hybrid_alpha": HYBRID_ALPHA,
                "hybrid_beta": HYBRID_BETA,
                "hybrid_gamma": HYBRID_GAMMA,
                "graph_depth": GRAPH_DEPTH,
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()

    for query_id, query, slug in QRELS:
        expected = f"concepts/{slug}.md"

        fts_hits = indexlib.search(query, fts_db, k=CANDIDATE_K)["candidates"]
        lexical = [{"path": hit["path"], "score": None, "score_kind": "not_exposed"} for hit in fts_hits]

        dense = dedupe_dense(indexlib.search_bundle(bundle, query, k=CANDIDATE_K, embed_fn=embedder))

        hybrid_rrf = rrf(lexical, dense)

        graph_out = graphlib.search_graph(graph_db, query, k=TOP_K, depth=GRAPH_DEPTH)
        graph_candidates = [
            {"path": item["path"], "score": item.get("graph_context", {}).get("distance"),
             "score_kind": "graph_distance"}
            for item in graph_out["candidates"]
        ]

        hybrid_out = indexlib.search_hybrid(
            bundle, query, k=TOP_K,
            alpha=HYBRID_ALPHA, beta=HYBRID_BETA, gamma=HYBRID_GAMMA,
            depth=GRAPH_DEPTH,
        )
        hybrid_candidates = [
            {"path": item["path"], "score": item.get("score"),
             "score_kind": "weighted_fusion"}
            for item in hybrid_out["candidates"]
        ]

        for stage, hits in (
            ("L1", lexical[:TOP_K]),
            ("L2", dense[:TOP_K]),
            ("L1+L2", hybrid_rrf),
            ("G", graph_candidates),
            ("G+L1", hybrid_candidates),
        ):
            output[stage].append({
                "run_id": stage,
                "query_id": query_id,
                "query": query,
                "expected_path": expected,
                "rank": rank_of(hits, expected),
                "candidate_paths": [hit["path"] for hit in hits],
                "stage_scores": [hit["score"] for hit in hits],
                "score_kind": hits[0]["score_kind"] if hits else "none",
                "mneme_version": __version__,
                "config_sha256": config_hash,
            })
    return output


def latency(
    bundle: Path, embedder: indexlib.Embedder, graph_db: Path, fts_db: Path,
) -> dict[str, dict[str, Any]]:
    data: dict[str, list[float]] = {stage: [] for stage in ("L1", "L2", "L1+L2", "G", "G+L1")}
    for _, query, _ in QRELS:
        for _ in range(QUERY_REPEATS):
            started = time.perf_counter()
            indexlib.search(query, fts_db, k=CANDIDATE_K)
            data["L1"].append((time.perf_counter() - started) * 1000)

            started = time.perf_counter()
            dedupe_dense(indexlib.search_bundle(bundle, query, k=CANDIDATE_K, embed_fn=embedder))
            data["L2"].append((time.perf_counter() - started) * 1000)

            started = time.perf_counter()
            current_fts = indexlib.search(query, fts_db, k=CANDIDATE_K)["candidates"]
            current_dense = dedupe_dense(
                indexlib.search_bundle(bundle, query, k=CANDIDATE_K, embed_fn=embedder)
            )
            rrf([{"path": hit["path"]} for hit in current_fts], current_dense)
            data["L1+L2"].append((time.perf_counter() - started) * 1000)

            started = time.perf_counter()
            graphlib.search_graph(graph_db, query, k=CANDIDATE_K, depth=GRAPH_DEPTH)
            data["G"].append((time.perf_counter() - started) * 1000)

            started = time.perf_counter()
            indexlib.search_hybrid(
                bundle, query, k=CANDIDATE_K,
                alpha=HYBRID_ALPHA, beta=HYBRID_BETA, gamma=HYBRID_GAMMA,
                depth=GRAPH_DEPTH,
            )
            data["G+L1"].append((time.perf_counter() - started) * 1000)
    return {
        stage: {
            "samples": len(values),
            "values_ms": values,
            "p50_ms": percentile(values, .5),
            "p95_ms": percentile(values, .95),
        }
        for stage, values in data.items()
    }


def graph_health_snapshot(graph_db: Path) -> dict[str, Any]:
    if not graph_db.is_file():
        return {"available": False}
    try:
        return {"available": True, **graphlib.graph_health(graph_db)}
    except Exception as exc:  # pragma: no cover - defensive
        return {"available": False, "error": str(exc)}


def report_html(
    manifest: dict[str, Any],
    rows: dict[str, list[dict[str, Any]]],
    metrics: dict[str, dict[str, float]],
    timing: dict[str, dict[str, Any]],
    p_values: dict[str, float],
) -> str:
    stages = ("L1", "L2", "L1+L2", "G", "G+L1")
    metrics_rows = "".join(
        f"<tr><th>{stage}</th>"
        f"<td>{metrics[stage]['Recall@1']:.3f}</td>"
        f"<td>{metrics[stage]['Recall@3']:.3f}</td>"
        f"<td>{metrics[stage]['Recall@10']:.3f}</td>"
        f"<td>{metrics[stage]['MRR@10']:.3f}</td>"
        f"<td>{metrics[stage]['nDCG@10']:.3f} [{metrics[stage]['nDCG_ci'][0]:.3f}, {metrics[stage]['nDCG_ci'][1]:.3f}]</td>"
        f"<td>{timing[stage]['p50_ms']:.2f}/{timing[stage]['p95_ms']:.2f}</td></tr>"
        for stage in stages
    )
    audit = "".join(
        f"<tr><td>{html.escape(row['query_id'])}</td><td>{html.escape(row['query'])}</td>"
        f"<td>{row['rank'] if row['rank'] is not None else '-'}</td>"
        f"<td>{rows['L2'][i]['rank'] if rows['L2'][i]['rank'] is not None else '-'}</td>"
        f"<td>{rows['L1+L2'][i]['rank'] if rows['L1+L2'][i]['rank'] is not None else '-'}</td>"
        f"<td>{rows['G'][i]['rank'] if rows['G'][i]['rank'] is not None else '-'}</td>"
        f"<td>{rows['G+L1'][i]['rank'] if rows['G+L1'][i]['rank'] is not None else '-'}</td></tr>"
        for i, row in enumerate(rows["L1"])
    )
    p_text = "；".join(f"{key} p={value:.3f}" for key, value in p_values.items())
    graph = manifest.get("graph_health", {})
    graph_text = (
        f"{graph.get('entity_count', 0)} entities / {graph.get('relation_count', 0)} relations / "
        f"{graph.get('connected_component_count', 0)} component(s) / "
        f"{graph.get('orphan_entity_count', 0)} orphan(s)"
        if graph.get("available") else "unavailable"
    )
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Mneme 跨版本检索回归 - 2026-07-20</title>
<style>
:root {{ --ink:#1b2a25; --muted:#5d6c65; --paper:#f5f5ef; --line:#d7ded8;
  --l1:#31736a; --l2:#9a5a27; --hybrid:#765297; --g:#2e637d; --gl1:#a83d2a; }}
body {{ margin:0; background:var(--paper); color:var(--ink);
  font:16px/1.65 -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif; }}
main {{ max-width:1100px; margin:auto; padding:52px 25px 84px; }}
h1 {{font-size:38px;line-height:1.15;margin:0 0 12px}} h2{{margin-top:46px}}
.meta{{color:var(--muted)}} .warning{{background:#fff0cf;border-left:5px solid #b87913;padding:17px 20px}}
table{{width:100%;border-collapse:collapse;background:white}}
th,td{{border:1px solid var(--line);padding:10px;text-align:left;vertical-align:top}}
th{{background:#e9efea}} code{{overflow-wrap:anywhere}}
.small{{font-size:14px;color:var(--muted)}}
</style></head><body><main>
<p class="meta">Mneme Research · Cross-version regression · {html.escape(manifest['created_at'])}</p>
<h1>0.5 / 2.0 / 3.0 / 4.0 的五题历史回归</h1>
<div class="warning"><strong>结论边界。</strong> 本报告只复跑五条历史手选 qrels，<strong>不是</strong>预注册主分析。
主分析仍缺 80 条、双人独立标注并裁决的 qrels，故不得将本页的均值、CI 或 p 值外推为主结论。
v0.5 原始分数（Recall@5=1.000 / MRR=0.800）在 manifest 中标记为"档案数字"，不在本表重新运行；
本表 L1/L2/L1+L2 与 2026-07-15-design01-historical 的对应阶段应可复现。</div>
<h2>冻结证据</h2>
<table><tr><th>字段</th><th>值</th></tr>
<tr><th>语料</th><td>{manifest['corpus']['source_files']} 篇私有 Markdown，{manifest['corpus']['total_characters']} 字符；聚合 SHA-256 <code>{manifest['corpus']['aggregate_sha256']}</code></td></tr>
<tr><th>表示</th><td>{manifest['concept_pages']} 个 Source 概念页；raw source 与系统文件已排除</td></tr>
<tr><th>实现</th><td>Mneme {manifest['mneme_version']}，commit <code>{manifest['code_revision']}</code>；BGE <code>{manifest['model']}</code>；RRF k={RRF_K}；hybrid α={HYBRID_ALPHA}/β={HYBRID_BETA}/γ={HYBRID_GAMMA}(inactive)；Graph depth={GRAPH_DEPTH}</td></tr>
<tr><th>Graph 健康</th><td>{graph_text}</td></tr>
<tr><th>索引成本</th><td>L1 中位 {manifest['index_ms']['L1']['median_ms']:.1f} ms / P95 {manifest['index_ms']['L1']['p95_ms']:.1f} ms / {manifest['index_ms']['L1']['bytes']} bytes；L2 中位 {manifest['index_ms']['L2']['median_ms']:.1f} ms / P95 {manifest['index_ms']['L2']['p95_ms']:.1f} ms / {manifest['index_ms']['L2']['bytes']} bytes；Graph 中位 {manifest['index_ms']['G']['median_ms']:.1f} ms / P95 {manifest['index_ms']['G']['p95_ms']:.1f} ms / {manifest['index_ms']['G']['bytes']} bytes</td></tr>
</table>
<h2>阶段定义</h2>
<table><tr><th>阶段</th><th>检索器</th><th>版本</th><th>状态</th></tr>
<tr><td>L1</td><td>SQLite FTS5</td><td>v2.0</td><td>零依赖词法基线</td></tr>
<tr><td>L2</td><td>BGE-small-zh-v1.5 + sqlite-vec</td><td>v3.0</td><td>纯语义检索</td></tr>
<tr><td>L1+L2</td><td>L1 与 L2，RRF k=60</td><td>v3.x 实验脚本</td><td>词法+语义融合</td></tr>
<tr><td>G</td><td>Graph BFS depth=2</td><td>v4.0</td><td>纯结构化召回</td></tr>
<tr><td>G+L1</td><td>Graph + FTS5 加权融合</td><td>v4.0 CLI 默认</td><td>v4.0 主候选</td></tr>
<tr><td>V0</td><td>v0.5 原始 dense</td><td>v0.5</td><td>档案数字，不在本表复跑</td></tr>
</table>
<h2>质量与延迟</h2>
<table><tr><th>阶段</th><th>Recall@1</th><th>Recall@3</th><th>Recall@10</th><th>MRR@10</th><th>nDCG@10 [bootstrap 95% CI]</th><th>查询 P50/P95 ms</th></tr>
{metrics_rows}</table>
<p class="small">每阶段 5 个历史 qrels；查询延迟为同一进程内 30 次 × 5 query 的 warm 样本，不含模型下载。配对随机化：{p_text}。样本极小，p 值仅作审计记录。</p>
<h2>逐题审计</h2>
<table><tr><th>ID</th><th>查询</th><th>L1</th><th>L2</th><th>L1+L2</th><th>G</th><th>G+L1</th></tr>{audit}</table>
<h2>解释</h2>
<p>本表 L1/L2/L1+L2 应与 2026-07-15-design01-historical 对应阶段一致（除随机扰动）。G 与 G+L1 是 v4.0 新增阶段。
若 G 在多跳题上 rank 优于 L1，提示 Graph 结构化召回有潜力，但需 80 题主分析验证。若 G+L1 的 nDCG@10 不低于 L1 且延迟可接受，提示 hybrid 路径值得作为 v4.0 默认。</p>
<h2>产物</h2>
<p><code>2026-07-20-cross-version-historical.manifest.json</code> 记录语料 hash、依赖、参数、Graph 健康度与环境；
<code>results.jsonl</code> 逐阶段记录 query、rank、path、score 与配置 hash；均不含私有语料正文。</p>
</main></body></html>"""


def run(corpus: Path, out: Path) -> None:
    if not corpus.is_dir():
        raise SystemExit(f"语料目录不存在：{corpus}")
    out.mkdir(parents=True, exist_ok=True)
    created_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    manifest: dict[str, Any] = {
        "created_at": created_at,
        "corpus": corpus_digest(corpus),
        "mneme_version": __version__,
        "code_revision": git_revision(),
        "runner_sha256": file_sha256(Path(__file__)),
        "bootstrap_sha256": file_sha256(ROOT / "scripts" / "bootstrap_dogfood.py"),
        "model": indexlib.DEFAULT_MODEL,
        "rrf_k": RRF_K,
        "top_k": TOP_K,
        "candidate_k": CANDIDATE_K,
        "hybrid_alpha": HYBRID_ALPHA,
        "hybrid_beta": HYBRID_BETA,
        "hybrid_gamma": HYBRID_GAMMA,
        "graph_depth": GRAPH_DEPTH,
        "python": sys.version,
        "platform": platform.platform(),
        "dependencies": dependency_lock(),
        "qrels": [
            {"id": ident, "query": query, "path": f"concepts/{slug}.md", "grade": 2}
            for ident, query, slug in QRELS
        ],
        "qrels_status": "historical hand-selected regression group; not independently double-annotated",
        "v0_5_archive_scores": {
            "source": "docs/superpowers/reports/2026-07-12-mneme-0.5.0-bench-results.md",
            "recall_at_1": 0.600,
            "recall_at_3": 1.000,
            "recall_at_5": 1.000,
            "mrr": 0.800,
            "note": "archive numbers from v0.5.0; not re-run here",
        },
    }
    with tempfile.TemporaryDirectory(prefix="mneme-cross-version-") as temp:
        bundle, config = Path(temp) / "wiki", Path(temp) / "config.toml"
        bootstrap(corpus, bundle, config)
        fts_paths = paths_for_fts(bundle)
        fts_times = []
        for _ in range(INDEX_RUNS):
            started = time.perf_counter()
            indexlib.reindex_paths(fts_paths, bundle)
            fts_times.append((time.perf_counter() - started) * 1000)
        embedder = indexlib.default_embed_fn()
        dense_times = []
        for _ in range(INDEX_RUNS):
            started = time.perf_counter()
            indexlib.reindex_bundle(bundle, embedder)
            dense_times.append((time.perf_counter() - started) * 1000)
        graph_times = []
        for _ in range(INDEX_RUNS):
            started = time.perf_counter()
            graphlib.rebuild_graph(bundle)
            graph_times.append((time.perf_counter() - started) * 1000)

        manifest["concept_pages"] = len(fts_paths)
        manifest["index_ms"] = {
            "L1": {
                "runs": fts_times,
                "median_ms": statistics.median(fts_times),
                "p95_ms": percentile(fts_times, .95),
                "bytes": indexlib.fts_index_path(bundle).stat().st_size,
            },
            "L2": {
                "runs": dense_times,
                "median_ms": statistics.median(dense_times),
                "p95_ms": percentile(dense_times, .95),
                "bytes": indexlib.l2_index_path(bundle).stat().st_size,
            },
            "G": {
                "runs": graph_times,
                "median_ms": statistics.median(graph_times),
                "p95_ms": percentile(graph_times, .95),
                "bytes": graphlib.graph_index_path(bundle).stat().st_size,
            },
        }
        graph_db = graphlib.graph_index_path(bundle)
        fts_db = indexlib.fts_index_path(bundle)
        manifest["graph_health"] = graph_health_snapshot(graph_db)

        rows = stage_rows(bundle, embedder, graph_db, fts_db)
        timing = latency(bundle, embedder, graph_db, fts_db)

    metrics = {stage: metric_values(stage_data) for stage, stage_data in rows.items()}
    for stage, stage_data in rows.items():
        metrics[stage]["nDCG_ci"] = bootstrap_ci(
            stage_data, lambda sampled: metric_values(sampled)["nDCG@10"]
        )
    p_values = {
        "L2-L1": paired_randomization(rows["L1"], rows["L2"]),
        "L1+L2-L1": paired_randomization(rows["L1"], rows["L1+L2"]),
        "G-L1": paired_randomization(rows["L1"], rows["G"]),
        "G+L1-L1": paired_randomization(rows["L1"], rows["G+L1"]),
        "G+L1-G": paired_randomization(rows["G"], rows["G+L1"]),
    }
    manifest["timing_ms"] = timing
    manifest["metrics"] = metrics
    manifest["paired_randomization_p"] = p_values

    stem = out / "2026-07-20-cross-version-historical"
    stem.with_suffix(".manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    with stem.with_suffix(".results.jsonl").open("w", encoding="utf-8") as handle:
        for stage in ("L1", "L2", "L1+L2", "G", "G+L1"):
            for row in rows[stage]:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    stem.with_suffix(".html").write_text(
        report_html(manifest, rows, metrics, timing, p_values), encoding="utf-8"
    )
    print(stem.with_suffix(".html"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--corpus", type=Path, default=Path("/Users/scott1743/Desktop/佳都/飞书文档库")
    )
    parser.add_argument("--out", type=Path, default=ROOT / "reports" / "experiments")
    run(**vars(parser.parse_args()))


if __name__ == "__main__":
    main()
