#!/usr/bin/env python3
"""Run the preregistered-design L1 pilot without copying private sources.

This is deliberately a pilot, not the Design 01 primary comparison: it
replays the five historical qrels on the available 142-document Feishu export
with Mneme's current FTS5 path. The runner writes only aggregate corpus
metadata, qrels, result paths, and measurements to the repository.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import os
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SKILL_SCRIPTS = ROOT / "skills" / "mneme" / "scripts"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SKILL_SCRIPTS))
os.environ["PYTHONPATH"] = str(SKILL_SCRIPTS) + os.pathsep + os.environ.get("PYTHONPATH", "")

from mneme import __version__, indexlib  # noqa: E402
from scripts.bootstrap_dogfood import bootstrap  # noqa: E402


HISTORICAL_QRELS = (
    ("gstack", "AKMedL4gzoLwNwxg1cyc9bdxnPI"),
    ("Claude Code 工作流", "AKMedL4gzoLwNwxg1cyc9bdxnPI"),
    ("银行回单", "UCvpdz5z8oZqXTxCpD2cLAObnse"),
    ("录音", "Sic7dPX3aoxVByxxWqqcZAQunRb"),
    ("Hermes", "XVFudUEQeoXQjixSS9zckeNonAg"),
)


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    return ordered[max(0, math.ceil(percentile * len(ordered)) - 1)]


def _corpus_manifest(corpus: Path) -> dict[str, Any]:
    digest = hashlib.sha256()
    total_chars = 0
    count = 0
    for source in sorted(corpus.glob("*.md")):
        data = source.read_bytes()
        digest.update(source.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(data).digest())
        total_chars += len(data.decode("utf-8"))
        count += 1
    return {
        "source_label": "private Feishu Markdown export",
        "source_path_not_published": True,
        "source_files": count,
        "total_characters": total_chars,
        "aggregate_sha256": digest.hexdigest(),
    }


def _indexable_paths(bundle: Path) -> list[Path]:
    paths: list[Path] = []
    for path in sorted(bundle.rglob("*.md")):
        if not path.is_file():
            continue
        parts = path.relative_to(bundle).parts
        if ".mneme" in parts or "sources" in parts or "external-sources" in parts:
            continue
        paths.append(path)
    return paths


def _git_revision() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def _metrics(rows: list[dict[str, Any]]) -> dict[str, float]:
    ranks = [row["rank"] for row in rows]
    metrics: dict[str, float] = {}
    for cutoff in (1, 3, 5, 10):
        metrics[f"recall_at_{cutoff}"] = sum(
            rank is not None and rank <= cutoff for rank in ranks
        ) / len(rows)
    metrics["mrr_at_10"] = statistics.mean(
        0.0 if rank is None else 1.0 / rank for rank in ranks
    )
    metrics["ndcg_at_10"] = statistics.mean(
        0.0 if rank is None else 1.0 / math.log2(rank + 1) for rank in ranks
    )
    return metrics


def _report_html(manifest: dict[str, Any], rows: list[dict[str, Any]], metrics: dict[str, float]) -> str:
    metric_rows = "".join(
        f"<tr><th>{html.escape(name)}</th><td>{value:.3f}</td></tr>"
        for name, value in metrics.items()
    )
    query_rows = "".join(
        "<tr>"
        f"<td><code>{html.escape(row['query'])}</code></td>"
        f"<td><code>{html.escape(row['expected_path'])}</code></td>"
        f"<td>{row['rank'] if row['rank'] is not None else 'not in top-10'}</td>"
        f"<td>{html.escape(', '.join(row['candidate_paths'][:3]))}</td>"
        "</tr>"
        for row in rows
    )
    timing = manifest["timing_ms"]
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Mneme L1 Pilot - 2026-07-15</title>
<style>
body {{ margin: 0; background: #f5f6f2; color: #1c2924; font: 16px/1.55 system-ui, sans-serif; }}
main {{ max-width: 960px; margin: 0 auto; padding: 52px 24px 72px; }}
h1 {{ font-size: 2.35rem; line-height: 1.08; margin: 0 0 10px; }} h2 {{ margin-top: 42px; }}
.flag {{ background: #fff4d8; border-left: 5px solid #ac6f00; padding: 14px 18px; }}
.meta {{ color: #53635b; }} table {{ width: 100%; border-collapse: collapse; background: #fff; }}
th, td {{ padding: 10px; border: 1px solid #d8dfd8; text-align: left; vertical-align: top; }}
th {{ background: #e8efe9; }} code {{ font-size: .9em; overflow-wrap: anywhere; }}
</style></head><body><main>
<p class="meta">Mneme retrieval research / Experiment 01 / {html.escape(manifest['created_at'])}</p>
<h1>L1 FTS5 historical-qrel pilot</h1>
<div class="flag"><strong>Scope limit.</strong> This is not the preregistered primary comparison. It replays only five historical hand-selected qrels on the available private corpus. It has no independently double-annotated 80-query set, no dense/hybrid run, no reranker, and no confidence interval or significance claim.</div>
<h2>Frozen input and runner</h2>
<table><tr><th>Field</th><th>Value</th></tr>
<tr><th>System</th><td>Mneme {html.escape(manifest['mneme_version'])}, persisted mode <code>fts5</code></td></tr>
<tr><th>Code revision</th><td><code>{html.escape(manifest['code_revision'])}</code></td></tr>
<tr><th>Corpus</th><td>{manifest['corpus']['source_files']} private Markdown files; {manifest['corpus']['total_characters']} characters; aggregate SHA-256 <code>{manifest['corpus']['aggregate_sha256']}</code></td></tr>
<tr><th>Representation</th><td>{manifest['concept_pages']} generated Source concept pages; raw sources excluded from the FTS5 index</td></tr>
<tr><th>Index build</th><td>{manifest['index']['runs']} rebuilds; median {manifest['index']['median_ms']:.1f} ms; P95 {manifest['index']['p95_ms']:.1f} ms; final cache {manifest['index']['bytes']} bytes</td></tr>
<tr><th>Query latency</th><td>in-process FTS5, {timing['samples']} samples; P50 {timing['p50']:.3f} ms; P95 {timing['p95']:.3f} ms</td></tr>
</table>
<h2>Retriever-only results</h2><table><tr><th>Metric</th><th>Value</th></tr>{metric_rows}</table>
<h2>Per-query audit</h2><table><tr><th>Query</th><th>Historical relevant page</th><th>Rank</th><th>Top-3 paths</th></tr>{query_rows}</table>
<h2>Interpretation</h2>
<p>The pilot measures only exact/historical lookup behavior. It can establish a reproducible FTS5 reference for this frozen corpus, but it cannot answer whether L2 semantic retrieval or L1+L2 fusion improves paraphrase, multi-hop, no-answer, or long-context retrieval. That requires the Design 01 corpus snapshot, at least 80 pre-run qrels with independent annotation, and separate L2 / L1+L2 / rerank runs.</p>
<h2>Artefacts</h2><p><code>2026-07-15-l1-pilot.manifest.json</code> records hashes and environment. <code>2026-07-15-l1-pilot.results.jsonl</code> contains the raw top-10 paths for each query. Neither artifact contains source text.</p>
</main></body></html>"""


def run(corpus: Path, out_dir: Path) -> None:
    if not corpus.is_dir():
        raise SystemExit(f"corpus directory not found: {corpus}")
    out_dir.mkdir(parents=True, exist_ok=True)
    created_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    corpus_info = _corpus_manifest(corpus)
    run_config = {
        "run_id": "L1",
        "mode": "fts5",
        "top_k": 10,
        "representation": "one generated Source concept page per raw Markdown source",
    }
    config_sha256 = hashlib.sha256(
        json.dumps(run_config, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()

    with tempfile.TemporaryDirectory(prefix="mneme-l1-pilot-") as temporary:
        work = Path(temporary)
        bundle, config = work / "wiki", work / "config.toml"
        bootstrap(corpus, bundle, config)
        paths = _indexable_paths(bundle)
        durations = []
        for _ in range(5):
            started = time.perf_counter()
            indexlib.reindex_paths(paths, bundle)
            durations.append((time.perf_counter() - started) * 1000)
        db_path = indexlib.fts_index_path(bundle)

        rows: list[dict[str, Any]] = []
        latency_samples: list[float] = []
        for query, expected_slug in HISTORICAL_QRELS:
            started = time.perf_counter()
            candidates = indexlib.search(query, db_path, k=10)["candidates"]
            elapsed_ms = (time.perf_counter() - started) * 1000
            expected_path = f"concepts/{expected_slug}.md"
            rank = next(
                (position for position, candidate in enumerate(candidates, start=1)
                 if candidate["path"] == expected_path),
                None,
            )
            rows.append({
                "run_id": "L1",
                "query": query,
                "expected_path": expected_path,
                "rank": rank,
                "stage_score": None,
                "stage_score_note": "Mneme public FTS5 candidate API does not expose bm25 scores",
                "elapsed_ms": elapsed_ms,
                "mneme_version": __version__,
                "config_sha256": config_sha256,
                "candidate_paths": [candidate["path"] for candidate in candidates],
            })
            for _ in range(30):
                started = time.perf_counter()
                indexlib.search(query, db_path, k=10)
                latency_samples.append((time.perf_counter() - started) * 1000)

        metrics = _metrics(rows)
        manifest = {
            "experiment_id": "2026-07-15-l1-pilot",
            "created_at": created_at,
            "design": "reports/designs/3.2-retrieval-comparison.html",
            "scope": "L1 pilot only; historical five-query qrels",
            "mneme_version": __version__,
            "code_revision": _git_revision(),
            "python": sys.version.split()[0],
            "corpus": corpus_info,
            "concept_pages": len(paths),
            "qrels": [{"query": query, "path": f"concepts/{slug}.md"} for query, slug in HISTORICAL_QRELS],
            "run_config": run_config,
            "run_config_sha256": config_sha256,
            "index": {
                "mode": "fts5",
                "path_not_published": ".mneme/fts.db",
                "runs": len(durations),
                "durations_ms": durations,
                "median_ms": statistics.median(durations),
                "p95_ms": _percentile(durations, 0.95),
                "bytes": db_path.stat().st_size,
            },
            "timing_ms": {
                "method": "in-process public FTS5 candidate API",
                "samples": len(latency_samples),
                "samples_values": latency_samples,
                "p50": _percentile(latency_samples, 0.50),
                "p95": _percentile(latency_samples, 0.95),
            },
        }

    stem = out_dir / "2026-07-15-l1-pilot"
    (stem.with_suffix(".manifest.json")).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    with stem.with_suffix(".results.jsonl").open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    stem.with_suffix(".html").write_text(
        _report_html(manifest, rows, metrics), encoding="utf-8"
    )
    print(f"wrote {stem.with_suffix('.html')}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--corpus", type=Path,
        default=Path("/Users/scott1743/Desktop/佳都/飞书文档库"),
    )
    parser.add_argument("--out", type=Path, default=ROOT / "reports" / "experiments")
    args = parser.parse_args()
    run(args.corpus, args.out)


if __name__ == "__main__":
    main()
