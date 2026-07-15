#!/usr/bin/env python3
"""Execute Design 01's reproducible historical-regression subset.

The full preregistered study requires 80 independently double-annotated qrels.
This runner deliberately does not fake that input. It executes the five
historical qrels through L1 FTS5, L2 semantic retrieval, and L1+L2 RRF, then writes a
Chinese report that separates this regression subset from the primary study.
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

from mneme import __version__, indexlib  # noqa: E402
from scripts.bootstrap_dogfood import bootstrap  # noqa: E402


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


def stage_rows(bundle: Path, embedder: indexlib.Embedder) -> dict[str, list[dict[str, Any]]]:
    output = {"L1": [], "L2": [], "L1+L2": []}
    config_hash = hashlib.sha256(
        json.dumps({"rrf_k": RRF_K, "top_k": TOP_K, "candidate_k": CANDIDATE_K}, sort_keys=True).encode()
    ).hexdigest()
    fts_db = indexlib.fts_index_path(bundle)
    for query_id, query, slug in QRELS:
        expected = f"concepts/{slug}.md"
        fts_hits = indexlib.search(query, fts_db, k=CANDIDATE_K)["candidates"]
        lexical = [{"path": hit["path"], "score": None, "score_kind": "not_exposed"} for hit in fts_hits]
        dense = dedupe_dense(indexlib.search_bundle(bundle, query, k=CANDIDATE_K, embed_fn=embedder))
        hybrid = rrf(lexical, dense)
        for stage, hits in (("L1", lexical[:TOP_K]), ("L2", dense[:TOP_K]), ("L1+L2", hybrid)):
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


def latency(bundle: Path, embedder: indexlib.Embedder) -> dict[str, dict[str, Any]]:
    fts_db = indexlib.fts_index_path(bundle)
    data: dict[str, list[float]] = {"L1": [], "L2": [], "L1+L2": []}
    for _, query, _ in QRELS:
        for _ in range(QUERY_REPEATS):
            started = time.perf_counter()
            lexical = indexlib.search(query, fts_db, k=CANDIDATE_K)["candidates"]
            data["L1"].append((time.perf_counter() - started) * 1000)

            started = time.perf_counter()
            dense_hits = dedupe_dense(indexlib.search_bundle(bundle, query, k=CANDIDATE_K, embed_fn=embedder))
            data["L2"].append((time.perf_counter() - started) * 1000)

            started = time.perf_counter()
            current_fts = indexlib.search(query, fts_db, k=CANDIDATE_K)["candidates"]
            current_dense = dedupe_dense(indexlib.search_bundle(bundle, query, k=CANDIDATE_K, embed_fn=embedder))
            rrf([{"path": hit["path"]} for hit in current_fts], current_dense)
            data["L1+L2"].append((time.perf_counter() - started) * 1000)
    return {
        stage: {
            "samples": len(values),
            "values_ms": values,
            "p50_ms": percentile(values, .5),
            "p95_ms": percentile(values, .95),
        }
        for stage, values in data.items()
    }


def svg_overview(
    metrics: dict[str, dict[str, float]],
    timing: dict[str, dict[str, Any]],
    index_ms: dict[str, dict[str, Any]],
) -> str:
    """Render the quality, latency distribution, and build cost in one view."""
    stages = ("L1", "L2", "L1+L2")
    colors = {"L1": "#31736a", "L2": "#9a5a27", "L1+L2": "#765297"}
    quality_x, quality_width = 142, 254
    latency_x, latency_width = 520, 332
    rows = (103, 188, 273)
    log_min, log_max = math.log2(0.2), math.log2(64)

    def latency_x_for(value: float) -> float:
        return latency_x + (math.log2(max(value, 0.2)) - log_min) / (log_max - log_min) * latency_width

    parts = [
        '<svg viewBox="0 0 920 348" role="img" '
        'aria-label="L1、L2、L1+L2 的检索质量、查询延迟分布与索引构建成本概览">',
        '<text x="142" y="31" font-size="14" font-weight="700">检索质量</text>',
        '<text x="142" y="48" font-size="12">nDCG@10，历史 5 题</text>',
        '<text x="520" y="31" font-size="14" font-weight="700">查询延迟分布</text>',
        '<text x="520" y="48" font-size="12">150 个 warm 样本，横轴为对数毫秒</text>',
    ]
    for tick in (0, 0.5, 1):
        x = quality_x + quality_width * tick
        parts.append(f'<line x1="{x:.1f}" y1="62" x2="{x:.1f}" y2="300" stroke="#d7ded8"/>')
        parts.append(f'<text x="{x:.1f}" y="322" text-anchor="middle" font-size="11">{tick:.1f}</text>')
    for tick in (0.25, 0.5, 1, 2, 4, 8, 16, 32, 64):
        x = latency_x_for(tick)
        parts.append(f'<line x1="{x:.1f}" y1="62" x2="{x:.1f}" y2="300" stroke="#e4e9e5"/>')
        parts.append(f'<text x="{x:.1f}" y="322" text-anchor="middle" font-size="11">{tick:g}</text>')
    for stage, y in zip(stages, rows):
        color = colors[stage]
        quality = metrics[stage]["nDCG@10"]
        values = sorted(timing[stage]["values_ms"])
        p50, p95 = timing[stage]["p50_ms"], timing[stage]["p95_ms"]
        build_seconds = index_ms["L1" if stage == "L1" else "L2"]["median_ms"] / 1000
        parts.append(f'<line x1="18" y1="{y + 40}" x2="886" y2="{y + 40}" stroke="#d7ded8"/>')
        parts.append(f'<text x="18" y="{y - 4}" font-size="16" font-weight="700">{stage}</text>')
        parts.append(f'<text x="18" y="{y + 15}" font-size="11">建索引 {build_seconds:.2f}s</text>')
        parts.append(
            f'<rect x="{quality_x}" y="{y - 17}" width="{quality_width * quality:.1f}" height="18" '
            f'fill="{color}" opacity="0.88"/>'
        )
        parts.append(f'<text x="{quality_x + quality_width + 12}" y="{y - 3}" font-size="13">{quality:.3f}</text>')
        for sample_index, value in enumerate(values):
            jitter = ((sample_index * 17) % 19 - 9) * 0.78
            parts.append(
                f'<circle cx="{latency_x_for(value):.1f}" cy="{y + jitter:.1f}" r="1.9" '
                f'fill="{color}" opacity="0.34"/>'
            )
        p50_x, p95_x = latency_x_for(p50), latency_x_for(p95)
        parts.append(f'<line x1="{p50_x:.1f}" y1="{y - 25}" x2="{p95_x:.1f}" y2="{y - 25}" stroke="{color}" stroke-width="3"/>')
        parts.append(f'<circle cx="{p50_x:.1f}" cy="{y - 25}" r="4" fill="{color}"/>')
        parts.append(f'<line x1="{p95_x:.1f}" y1="{y - 32}" x2="{p95_x:.1f}" y2="{y - 18}" stroke="{color}" stroke-width="2"/>')
        parts.append(f'<text x="{latency_x + latency_width + 13}" y="{y - 17}" font-size="11">P50 {p50:.2f}</text>')
        parts.append(f'<text x="{latency_x + latency_width + 13}" y="{y - 3}" font-size="11">P95 {p95:.2f}</text>')
    parts.extend([
        '<text x="142" y="342" font-size="11">低</text>',
        '<text x="396" y="342" text-anchor="end" font-size="11">高</text>',
        '<text x="520" y="342" font-size="11">快</text>',
        '<text x="852" y="342" text-anchor="end" font-size="11">慢</text>',
        '</svg>',
    ])
    return "".join(parts)


def report_html(manifest: dict[str, Any], rows: dict[str, list[dict[str, Any]]], metrics: dict[str, dict[str, float]], timing: dict[str, dict[str, Any]], p_values: dict[str, float]) -> str:
    metrics_rows = "".join(
        f"<tr><th>{stage}</th><td>{values['Recall@1']:.3f}</td><td>{values['Recall@3']:.3f}</td><td>{values['Recall@10']:.3f}</td><td>{values['MRR@10']:.3f}</td><td>{values['nDCG@10']:.3f} [{values['nDCG_ci'][0]:.3f}, {values['nDCG_ci'][1]:.3f}]</td><td>{timing[stage]['p50_ms']:.2f}/{timing[stage]['p95_ms']:.2f}</td></tr>"
        for stage, values in metrics.items()
    )
    audit = "".join(
        f"<tr><td>{html.escape(row['query_id'])}</td><td>{html.escape(row['query'])}</td><td>{row['L1'] or '—'}</td><td>{row['L2'] or '—'}</td><td>{row['L1+L2'] or '—'}</td></tr>"
        for row in ({
            "query_id": q["query_id"], "query": q["query"],
            "L1": q["rank"], "L2": rows["L2"][i]["rank"], "L1+L2": rows["L1+L2"][i]["rank"],
        } for i, q in enumerate(rows["L1"]))
    )
    p_text = "；".join(f"{key} p={value:.3f}" for key, value in p_values.items())
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Mneme 检索比较实验执行报告</title>
<style>
:root {{ --ink:#1b2a25; --muted:#5d6c65; --paper:#f5f5ef; --line:#d7ded8; --l1:#31736a; --l2:#9a5a27; --hybrid:#765297; }}
body {{ margin:0; background:var(--paper); color:var(--ink); font:16px/1.65 -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif; }} main {{ max-width:1050px;margin:auto;padding:52px 25px 84px; }} h1 {{font-size:40px;line-height:1.15;margin:0 0 12px}} h2{{margin-top:46px}} .meta{{color:var(--muted)}} .warning{{background:#fff0cf;border-left:5px solid #b87913;padding:17px 20px}} .ok{{background:#e7f2ed;border-left:5px solid var(--l1);padding:17px 20px}} table{{width:100%;border-collapse:collapse;background:white}}th,td{{border:1px solid var(--line);padding:10px;text-align:left;vertical-align:top}}th{{background:#e9efea}} code{{overflow-wrap:anywhere}} .chart{{background:#fcfdfb;padding:20px 18px;border:1px solid var(--line)}} svg{{width:100%;max-width:500px}} .overview-chart svg{{max-width:920px}} .small{{font-size:14px;color:var(--muted)}}
</style></head><body><main>
<p class="meta">Mneme Research · Design 01 执行报告 · {html.escape(manifest['created_at'])}</p><h1>检索不是一个分数：<br>L1、L2 与 L1+L2 的历史回归执行</h1>
<div class="warning"><strong>结论边界。</strong> 本报告完成了设计中可复跑的历史 5-query 回归组与 L1 / L2 / L1+L2 工程对比；它<strong>不是</strong>预注册主分析。主分析仍缺 80 条、双人独立标注并裁决的 qrels，故不得将本页的均值、CI 或 p 值外推为主结论。未执行 rerank：发行物没有 reranker。</div>
<h2>执行对象与冻结证据</h2><table><tr><th>字段</th><th>值</th></tr><tr><th>语料</th><td>{manifest['corpus']['source_files']} 篇私有 Markdown，{manifest['corpus']['total_characters']} 字符；聚合 SHA-256 <code>{manifest['corpus']['aggregate_sha256']}</code></td></tr><tr><th>表示</th><td>{manifest['concept_pages']} 个 Source 概念页；已排除原始资料及系统文件</td></tr><tr><th>实现</th><td>Mneme {manifest['mneme_version']}，commit <code>{manifest['code_revision']}</code>；BGE <code>{manifest['model']}</code>；RRF k={RRF_K}</td></tr><tr><th>执行脚本</th><td>runner <code>{manifest['runner_sha256']}</code>；导入器 <code>{manifest['bootstrap_sha256']}</code></td></tr><tr><th>索引成本</th><td>L1：中位 {manifest['index_ms']['L1']['median_ms']:.1f} ms / P95 {manifest['index_ms']['L1']['p95_ms']:.1f} ms / {manifest['index_ms']['L1']['bytes']} bytes；L2：中位 {manifest['index_ms']['L2']['median_ms']:.1f} ms / P95 {manifest['index_ms']['L2']['p95_ms']:.1f} ms / {manifest['index_ms']['L2']['bytes']} bytes</td></tr></table>
<h2>阶段定义</h2><table><tr><th>阶段</th><th>检索器</th><th>状态</th></tr><tr><td>L1</td><td>SQLite FTS5</td><td>零依赖词法基线</td></tr><tr><td>L2</td><td>BGE-small-zh-v1.5 + sqlite-vec</td><td>纯语义检索</td></tr><tr><td>L1+L2</td><td>L1 与 L2，Reciprocal Rank Fusion</td><td>RRF k=60；混合检索的可运行子集</td></tr><tr><td>L1+L2+rerank</td><td>混合检索 + cross-encoder</td><td>未实现，不报告数值</td></tr></table>
<h2>质量、延迟与构建成本</h2><div class="chart overview-chart">{svg_overview(metrics, timing, manifest['index_ms'])}</div><p class="small">每行同时呈现 nDCG@10、150 个 warm 查询样本、P50/P95 与索引构建中位数。延迟横轴采用对数刻度；完整样本数组保存在 manifest。</p><table><tr><th>阶段</th><th>Recall@1</th><th>Recall@3</th><th>Recall@10</th><th>MRR@10</th><th>nDCG@10 [bootstrap 95% CI]</th><th>查询 P50/P95 ms</th></tr>{metrics_rows}</table><p class="small">每个阶段 5 个历史 qrels；查询延迟为同一进程内 30 次 × 5 query，不包含首次模型下载。配对随机化：{p_text}。样本极小，p 值仅作审计记录。</p>
<h2>逐题审计</h2><table><tr><th>ID</th><th>查询</th><th>L1 排名</th><th>L2 排名</th><th>L1+L2 排名</th></tr>{audit}</table>
<h2>解释</h2><div class="ok"><strong>可以说：</strong>这套固定语料、固定概念页表示和固定历史 qrels 上，三段检索器均已真实运行，并有可追溯原始结果、依赖锁定和成本数据。<br><strong>不能说：</strong>L1+L2 已在真实中文资料上得到可证明的净收益，或任一系统优于另一系统的总体结论。要达到设计门槛，下一步必须先冻结并双人标注 80 条分层 qrels，再重跑 L2 与 L1+L2，并按 query 类型报告。</div>
<h2>产物</h2><p><code>2026-07-15-design01-historical.manifest.json</code> 记录语料 hash、依赖、参数和环境；<code>results.jsonl</code> 逐阶段记录 query、rank、path、score 与配置 hash；所有数据均不含私有语料正文。</p></main></body></html>"""


def run(corpus: Path, out: Path) -> None:
    if not corpus.is_dir():
        raise SystemExit(f"语料目录不存在：{corpus}")
    out.mkdir(parents=True, exist_ok=True)
    created_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    manifest: dict[str, Any] = {"created_at": created_at, "corpus": corpus_digest(corpus), "mneme_version": __version__, "code_revision": git_revision(), "runner_sha256": file_sha256(Path(__file__)), "bootstrap_sha256": file_sha256(ROOT / "scripts" / "bootstrap_dogfood.py"), "model": indexlib.DEFAULT_MODEL, "rrf_k": RRF_K, "top_k": TOP_K, "candidate_k": CANDIDATE_K, "python": sys.version, "platform": platform.platform(), "dependencies": dependency_lock(), "qrels": [{"id": ident, "query": query, "path": f"concepts/{slug}.md", "grade": 2} for ident, query, slug in QRELS], "qrels_status": "historical hand-selected regression group; not independently double-annotated"}
    with tempfile.TemporaryDirectory(prefix="mneme-design01-") as temp:
        bundle, config = Path(temp) / "wiki", Path(temp) / "config.toml"
        bootstrap(corpus, bundle, config)
        fts_paths = paths_for_fts(bundle)
        fts_times = []
        for _ in range(INDEX_RUNS):
            started = time.perf_counter(); indexlib.reindex_paths(fts_paths, bundle); fts_times.append((time.perf_counter() - started) * 1000)
        embedder = indexlib.default_embed_fn()
        dense_times = []
        for _ in range(INDEX_RUNS):
            started = time.perf_counter(); indexlib.reindex_bundle(bundle, embedder); dense_times.append((time.perf_counter() - started) * 1000)
        manifest["concept_pages"] = len(fts_paths)
        manifest["index_ms"] = {"L1": {"runs": fts_times, "median_ms": statistics.median(fts_times), "p95_ms": percentile(fts_times, .95), "bytes": indexlib.fts_index_path(bundle).stat().st_size}, "L2": {"runs": dense_times, "median_ms": statistics.median(dense_times), "p95_ms": percentile(dense_times, .95), "bytes": indexlib.l2_index_path(bundle).stat().st_size}}
        rows = stage_rows(bundle, embedder)
        timing = latency(bundle, embedder)
    metrics = {stage: metric_values(stage_data) for stage, stage_data in rows.items()}
    for stage, stage_data in rows.items():
        metrics[stage]["nDCG_ci"] = bootstrap_ci(stage_data, lambda sampled: metric_values(sampled)["nDCG@10"])
    p_values = {"L2-L1": paired_randomization(rows["L1"], rows["L2"]), "L1+L2-L1": paired_randomization(rows["L1"], rows["L1+L2"]), "L1+L2-L2": paired_randomization(rows["L2"], rows["L1+L2"])}
    manifest["timing_ms"] = timing; manifest["metrics"] = metrics; manifest["paired_randomization_p"] = p_values
    stem = out / "2026-07-15-design01-historical"
    stem.with_suffix(".manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with stem.with_suffix(".results.jsonl").open("w", encoding="utf-8") as handle:
        for stage in ("L1", "L2", "L1+L2"):
            for row in rows[stage]: handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    stem.with_suffix(".html").write_text(report_html(manifest, rows, metrics, timing, p_values), encoding="utf-8")
    print(stem.with_suffix(".html"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=Path("/Users/scott1743/Desktop/佳都/飞书文档库"))
    parser.add_argument("--out", type=Path, default=ROOT / "reports" / "experiments")
    run(**vars(parser.parse_args()))


if __name__ == "__main__": main()
