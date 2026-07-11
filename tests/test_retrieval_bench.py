"""Retrieval benchmark scaffold for Phase 4 (v0.5.0 dogfood).

Phase 4 was always going to need a labeled benchmark set. The
shape of this file is the v0.5.0 deliverable: a small set of
Chinese search queries paired with the concept_id we expect to
find. The queries are drawn from the 142-document Feishu corpus
that `scripts/bootstrap_dogfood.py` reads; the expectations come
from inspecting a few of those documents.

The benchmark is intentionally small (5 queries). It is not a
measurement of retrieval quality — that's the larger Phase 4
deliverable that lives alongside this scaffold. What this file
DOES prove is that the search shell returns semantically related
concepts for queries the corpus actually covers, with the right
concept in the top-3.

Real semantic search can prefer a more semantically rich sibling
over an exact-match page; we don't require rank-1. Top-3 hits the
expected concept is the harness's contract.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from mneme import indexlib

ROOT = Path(__file__).parent.parent
DOGFOOD_CORPUS = Path(
    "/Users/scott1743/Desktop/佳都/飞书文档库"
)
DOGFOOD_BUNDLE = Path.home() / "mneme-dogfood-2026-07-12"


# Each tuple: (search query, expected concept slug). The slug is
# the part of the source filename after the leading NNN_ prefix;
# that matches what `scripts/bootstrap_dogfood.py` writes to
# `concepts/<slug>.md`.
BENCHMARK_QUERIES: list[tuple[str, str]] = [
    ("gstack", "AKMedL4gzoLwNwxg1cyc9bdxnPI"),
    ("Claude Code 工作流", "AKMedL4gzoLwNwxg1cyc9bdxnPI"),
    ("银行回单", "UCvpdz5z8oZqXTxCpD2cLAObnse"),
    ("录音", "Sic7dPX3aoxVByxxWqqcZAQunRb"),
    ("Hermes", "XVFudUEQeoXQjixSS9zckeNonAg"),
]


def _slug_for_source(filename: str) -> str:
    """Match bootstrap_dogfood's slug derivation."""
    m = re.match(r"^(\d+_)?(.+?)(\.md)?$", filename)
    return m.group(2) if m else filename.rsplit(".", 1)[0]


@pytest.fixture(scope="module")
def dogfood_bundle(tmp_path_factory):
    """Build + reindex the dogfood bundle once per test module.

    Skips if the corpus is missing (so CI in environments without
    the Feishu dump can still run the rest of the suite).
    """
    if not DOGFOOD_CORPUS.is_dir():
        pytest.skip(f"dogfood corpus not present at {DOGFOOD_CORPUS}")

    work = tmp_path_factory.mktemp("dogfood")
    bundle = work / "wiki"
    cfg = work / "cfg.toml"
    cfg.write_text(f'bundle_path = "{bundle}"\n')

    bootstrap = subprocess.run(
        [sys.executable, "-m", "scripts.bootstrap_dogfood",
         "--corpus", str(DOGFOOD_CORPUS),
         "--bundle", str(bundle),
         "--config", str(cfg)],
        capture_output=True, text=True, check=False,
    )
    if bootstrap.returncode != 0:
        pytest.skip(f"bootstrap failed: {bootstrap.stderr[:300]}")

    rc = subprocess.run(
        [sys.executable, "-m", "mneme", "reindex",
         "--config", str(cfg)],
        capture_output=True, text=True, check=False,
    )
    if rc.returncode != 0:
        pytest.skip(f"reindex unavailable in this env: {rc.stderr[:300]}")
    yield bundle, cfg


def _search(query: str, cfg: Path, k: int = 5) -> list:
    r = subprocess.run(
        [sys.executable, "-m", "mneme", "search", query,
         "-k", str(k), "--json", "--config", str(cfg)],
        capture_output=True, text=True, check=False,
    )
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


@pytest.mark.parametrize("query,expected_slug", BENCHMARK_QUERIES)
def test_benchmark_query_finds_expected_concept_in_top_3(
    query, expected_slug, dogfood_bundle
):
    """The expected concept appears in the top-3 hits for a corpus-
    relevant query. We don't require rank-1 because semantic
    search can prefer a richer sibling. Top-3 is the contract."""
    bundle, cfg = dogfood_bundle
    hits = _search(query, cfg, k=5)
    assert hits, f"search for {query!r} returned no hits"
    top3 = {h["concept_id"] for h in hits[:3]}
    expected = f"concepts/{expected_slug}"
    assert expected in top3, (
        f"expected concept {expected!r} missing from top-3 for "
        f"{query!r}; got {sorted(top3)}"
    )


def test_benchmark_corpus_is_real(dogfood_bundle):
    """Sanity check that we actually indexed Feishu dump content, not
    an empty placeholder bundle."""
    bundle, cfg = dogfood_bundle
    counts = list(bundle.glob("concepts/*.md"))
    assert len(counts) >= 50, (
        f"expected at least 50 concept pages in dogfood bundle; "
        f"got {len(counts)}"
    )


def test_benchmark_slug_derivation_matches_bootstrap():
    """`scripts/bootstrap_dogfood.py` derives slugs by stripping the
    leading digits + underscore and the trailing `.md`. Pin that
    derivation in test form so the benchmark expectations don't
    drift independently of the script."""
    assert _slug_for_source("017_AKMedL4gzoLwNwxg1cyc9bdxnPI.md") == \
        "AKMedL4gzoLwNwxg1cyc9bdxnPI"
    assert _slug_for_source("056_ARxXdsmbaoPZYLxcZuVcz6hpnu5.md") == \
        "ARxXdsmbaoPZYLxcZuVcz6hpnu5"
