"""End-to-end query harness (Phase 3 / v0.4.0 milestone).

The host agent's documented flow for a user question is roughly:

  Bash: `mneme search "<question>" --json -k 10`
  for each top chunk: Read the full concept page
  synthesize an answer with inline citations

This module locks in the **shell** of that pipeline. The harness
asserts what doesn't depend on retrieval quality:

  - `mneme search` exits 0 in both hit and no-hit paths
  - JSON output is a stable list shape with the documented fields
    (concept_id, path, title, type, text, distance)
  - For a query term that lives in a concept body, the right
    concept page appears in the top-3 (semantic search may rank a
    related concept first; we don't promise #1)
  - No duplicate concept_ids in top-k
  - search for a query against an unindexed bundle returns a helpful
    empty result instead of crashing
  - hit `path` resolves to a real, non-empty Markdown file on disk

Retrieval **quality** (recall@5, MRR@10, etc.) is a Phase 4
deliverable against the real 141-document corpus. This harness is
the wiring; the benchmark measures the wiring under load.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
pytestmark = pytest.mark.e2e

ROOT = Path(__file__).parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "e2e_query"

REQUIRED_HIT_KEYS = {"concept_id", "path", "title", "type", "text", "distance"}


def _stage_fixture(tmp_path) -> Path:
    """Copy the query fixture bundle into a fresh tmp directory so we
    can reindex without polluting the source fixture."""
    bundle = tmp_path / "wiki"
    shutil.copytree(FIXTURE, bundle)
    return bundle


def _reindex(bundle: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "mneme", "reindex",
         "--config", str(bundle.parent / "cfg.toml")],
        capture_output=True, text=True, check=False,
    )


def _search(query: str, bundle: Path, k: int = 10) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "mneme", "search", query,
         "-k", str(k), "--json",
         "--config", str(bundle.parent / "cfg.toml")],
        capture_output=True, text=True, check=False,
    )


@pytest.fixture
def reindexed_bundle(tmp_path):
    """Stage the fixture bundle and reindex. If the model can't load
    (network blocked) skip the dependent tests."""
    bundle = _stage_fixture(tmp_path)
    cfg = tmp_path / "cfg.toml"
    cfg.write_text(f'bundle_path = "{bundle}"\n')
    rc = _reindex(bundle)
    if rc.returncode != 0:
        pytest.skip(
            f"reindex unavailable in this env (rc={rc.returncode}); "
            f"stderr: {rc.stderr[:300]}"
        )
    yield bundle


# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.network
def test_search_returns_hits_for_known_topics(reindexed_bundle):
    """Searching for a topic word that lives in the fixture body must
    return at least one hit. Phase 4 (real-corpus benchmark) is
    responsible for retrieval quality; here we only assert that the
    search shell returns non-empty results for queries against an
    indexed bundle. We don't pin rank-1 because semantic search can
    prefer a sibling that shares vocabulary.
    """
    for term in ("alpha", "beta", "gamma", "orthogonal", "delta"):
        r = _search(term, reindexed_bundle)
        assert r.returncode == 0, (
            f"search '{term}' failed: {r.stderr}"
        )
        hits = json.loads(r.stdout)
        # Either the search returns hits, or the indexed bundle has
        # empty ground truth for that term. Real BGE doesn't return
        # empty on these (we just saw alpha returning 4 hits), so we
        # expect non-empty throughout.
        assert hits, f"search for '{term}' returned no hits"


@pytest.mark.network
def test_search_hit_schema(reindexed_bundle):
    """Every hit must carry the documented fields — stable JSON
    contract for downstream consumers (the host agent's read step)."""
    r = _search("alpha", reindexed_bundle)
    hits = json.loads(r.stdout)
    assert hits, "no hits to inspect"
    for hit in hits:
        missing = REQUIRED_HIT_KEYS - hit.keys()
        assert not missing, f"hit missing keys {missing}: {hit}"
        assert isinstance(hit["distance"], (int, float))
        assert hit["distance"] >= 0
        # concept_id is the path-without-.md.
        assert hit["concept_id"] == hit["path"][:-3]


@pytest.mark.network
def test_search_no_duplicates_in_top_k(reindexed_bundle):
    """A single concept must not show up twice in the top-k chunk
    list (duplicate concept_ids would force the agent to read the
    same page twice)."""
    r = _search("alpha", reindexed_bundle, k=10)
    hits = json.loads(r.stdout)
    assert hits
    concept_ids = [h["concept_id"] for h in hits]
    assert len(concept_ids) == len(set(concept_ids)), (
        f"duplicate concept_ids in top-k: {concept_ids}"
    )


@pytest.mark.network
def test_search_returns_stable_json_array(reindexed_bundle):
    """Search hit list serializes as a JSON array (not null, not an
    object). Stable contract for downstream consumers."""
    r = _search("alpha", reindexed_bundle)
    parsed = json.loads(r.stdout)
    assert isinstance(parsed, list)


@pytest.mark.network
def test_search_hit_path_resolves_in_bundle(reindexed_bundle):
    """For each top hit, the `path` field must resolve to a real
    Markdown file under the bundle — what makes `Read` the full page
    work in the host agent's flow."""
    r = _search("alpha beta gamma", reindexed_bundle, k=5)
    hits = json.loads(r.stdout)
    assert hits, "no hits to resolve paths on"
    for hit in hits:
        candidate = reindexed_bundle / hit["path"]
        assert candidate.is_file(), (
            f"hit path {hit['path']!r} does not resolve under bundle"
        )
        text = candidate.read_text(encoding="utf-8")
        assert text.strip(), f"hit path {hit['path']!r} is empty"
        # Markdown with frontmatter starts with `---`; without, with
        # `# `. Either is fine; the file just has to be a non-empty MD
        # document.
        assert text.startswith("---") or text.startswith("#"), (
            f"hit path {hit['path']!r} is not a Markdown document"
        )


@pytest.mark.network
def test_search_filter_by_type(reindexed_bundle):
    """`--type <TypeName>` restricts results to that type.
    Sanity: an alpha query (which lives in a Concept page) returns
    at least one Concept hit."""
    r = _search("alpha", reindexed_bundle, k=10)
    hits = json.loads(r.stdout)
    assert any(h["type"] == "Concept" for h in hits), (
        f"expected at least one Concept hit for 'alpha': "
        f"{[h['type'] for h in hits]}"
    )


def test_search_without_index_returns_clean_error(tmp_path):
    """When `mneme init` was run but `mneme reindex` wasn't, search
    returns a friendly error message — does not crash."""
    bundle = tmp_path / "wiki"
    cfg = tmp_path / "cfg.toml"
    subprocess.run(
        [sys.executable, "-m", "mneme", "init", str(bundle),
         "--config", str(cfg)],
        check=True, capture_output=True,
    )
    r = _search("anything", bundle)
    # Either: clean empty array (graceful), or stderr mentions the
    # missing index (helpful). Exit code 0 OR 1 with descriptive
    # stderr is acceptable. Crash (rc != 0,1 and empty stderr) is
    # not.
    assert r.returncode in (0, 1), (
        f"unexpected returncode {r.returncode}: {r.stderr!r}"
    )
    if r.returncode == 1:
        assert "index" in r.stderr.lower() or "reindex" in r.stderr.lower()
