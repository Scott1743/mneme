"""End-to-end black-box test against a 10-document news corpus.

The corpus lives under ``tests/fixtures/blackbox_news/`` and covers
ten distinct domains (technology, finance, sports, culture, health,
international, education, environment, politics, entertainment) so a
single ingest → search → lint pass exercises the contract across
enough semantic variety that a regression in chunking, indexing, or
orphan analysis is unlikely to hide behind a narrow topic.

What this module pins, in order:

  1. **init** — ``mneme init`` scaffolds a valid empty bundle.
  2. **ingest (write)** — ``scripts.bootstrap_dogfood`` distills the
     10 raw sources into 10 ``type: Source`` concept pages, copies
     each source into ``sources/``, extends ``index.md``, and
     prepends 10 entries to ``log.md``. This is the deterministic
     equivalent of the SKILL.md ingest scenario — the host agent
     would do the LLM-driven distillation, but the file-system
     contract (copy / write / index / prepend) is identical.
  3. **search** — ``mneme reindex`` builds the L2 index with a
     deterministic embedder (no network, no model download) and
     ``mneme search`` returns the expected concept in the top-3 for
     each domain-specific query.
  4. **lint** — ``mneme lint`` reports 0 errors and 0 orphans (every
     concept is reachable from ``index.md``).
  5. **dream** — ``mneme dream`` is **not a registered subcommand**.
     The v0.2.1rc1 freeze removed it; 1.0.0 keeps it removed. The
     contract is that the CLI exits with argparse's code 2
     ("invalid choice") rather than silently doing nothing or
     raising ``AttributeError``. A future dream resurrection must
     pass Phase 5 safety TDD first; until then, this test is the
     release-gate guard.

Each step is a subprocess call so the test exercises the actual CLI
surface, not just the library API. A failure here means a user
following the quickstart would hit the same failure.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.compat, pytest.mark.l2]

from mneme import cli
# v1.1.0 switched CLI entry from `mneme <cmd>` console command to
# `python3 ~/.claude/skills/mneme/scripts/mneme.py <cmd>`. These
# subprocess tests still call the old form and need a rewrite
# (PR2 / PR3 work). Default-skipped per pyproject.toml addopts.
pytestmark = [pytest.mark.e2e, pytest.mark.compat, pytest.mark.l2]

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests" / "fixtures" / "blackbox_news"

# Each tuple: (search query, expected slug, keywords). Slug derivation
# matches ``scripts.bootstrap_dogfood._slug_for`` — leading ``NN_``
# prefix and trailing ``.md`` are stripped. Keywords drive the
# deterministic embedder below: both concept chunks and search queries
# are projected onto the same keyword-count vector, so cosine
# similarity ranks the matching concept highest.
EXPECTED_CONCEPTS = [
    ("量子计算", "tech_quantum",
        ["量子", "qubit", "quantum", "马约拉纳", "拓扑"]),
    ("存款准备金率", "finance_central_bank",
        ["央行", "准备金", "存款", "降准", "货币"]),
    ("世界杯", "sports_world_cup",
        ["世界杯", "足球", "国足", "武磊"]),
    ("布克奖", "culture_booker",
        ["布克", "文学奖", "小说", "李雪"]),
    ("阿尔茨海默", "health_alzheimer",
        ["阿尔茨海默", "抗体", "认知", "ARIA"]),
    ("国际空间站", "intl_space_station",
        ["空间站", "NASA", "Roscosmos", "ESA", "微重力"]),
    ("高考改革", "education_gaokao",
        ["高考", "选科", "教育部", "物理", "历史"]),
    ("北极海冰", "env_arctic_ice",
        ["北极", "海冰", "NSIDC", "反照率", "北极熊"]),
    ("欧洲议会 AI", "politics_election",
        ["欧洲议会", "AI 法案", "GPAI", "人工智能", "监管"]),
    ("山海异闻录", "entertainment_box_office",
        ["山海异闻录", "动画", "票房", "追光", "NeRF"]),
]


# ─────────────────────────────────────────────────────────────────────────────
# A deterministic embedder keyed on per-concept keyword lists. Each
# chunk is projected onto a 10-d vector whose slot i is the count of
# concept-i keywords appearing in the text. Search queries are
# projected the same way, so cosine similarity ranks the matching
# concept highest without downloading the BGE model.
# ─────────────────────────────────────────────────────────────────────────────

class NewsKeywordEmbedder:
    """Count-based embedder keyed on per-concept keyword lists.

    Each chunk is mapped to a 10-d vector whose slot i is the count
    of concept-i keywords appearing in the text. Search queries are
    projected the same way, so cosine similarity ranks the matching
    concept highest. Both the chunk side and the query side use the
    same projection, so dimensions and semantics match by
    construction.
    """

    def __init__(self):
        self.keywords = [kw for _, _, kw in EXPECTED_CONCEPTS]
        self.n = len(self.keywords)

    def embed(self, texts):
        out = []
        for t in texts:
            v = []
            for kws in self.keywords:
                v.append(float(sum(1 for kw in kws if kw in t)))
            # If a chunk matches no keyword, fall back to a uniform
            # 0.1 vector so cosine similarity is well-defined but
            # the chunk doesn't dominate any query.
            if sum(v) == 0:
                v = [0.1] * self.n
            out.append(v)
        return out


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def blackbox_bundle(tmp_path):
    """Init + ingest 10 news sources into a fresh bundle.

    Returns ``(bundle_path, cfg_path)`` so individual tests can
    reindex with the deterministic embedder and then drive search.

    Both ``mneme init`` and ``bootstrap_dogfood`` run as subprocesses
    so the test process's ``sys.modules`` stays clean — an earlier
    version imported ``bootstrap_dogfood`` in-process, which left
    ``scripts/`` on ``sys.path`` and broke ``hashlib`` lookup for the
    later ``from mneme import indexlib`` import.
    """
    if not CORPUS.is_dir():
        pytest.skip(f"blackbox corpus missing at {CORPUS}")
    sources = sorted(CORPUS.glob("*.md"))
    assert len(sources) == 10, (
        f"expected 10 fixture sources, found {len(sources)}: "
        f"{[s.name for s in sources]}"
    )

    bundle = tmp_path / "wiki"
    cfg = tmp_path / "cfg.toml"

    # Step 1: init
    subprocess.run(
        [sys.executable, "-m", "mneme", "init", str(bundle),
         "--config", str(cfg)],
        capture_output=True, text=True, check=True,
    )

    # Step 2: ingest via bootstrap_dogfood (deterministic distillation).
    # Run as a subprocess with cwd=ROOT so `python -m scripts.bootstrap_dogfood`
    # resolves; keeps the test process's sys.path / sys.modules clean.
    rc = subprocess.run(
        [sys.executable, "-m", "scripts.bootstrap_dogfood",
         "--corpus", str(CORPUS), "--bundle", str(bundle),
         "--config", str(cfg)],
        cwd=str(ROOT), capture_output=True, text=True, check=True,
    )

    return bundle, cfg


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_step_one_init_scaffolds_bundle(tmp_path):
    """``mneme init`` creates index.md, log.md, sources/ in a fresh
    bundle path. The first gate of the black-box flow."""
    bundle = tmp_path / "wiki"
    cfg = tmp_path / "cfg.toml"
    rc = subprocess.run(
        [sys.executable, "-m", "mneme", "init", str(bundle),
         "--config", str(cfg)],
        capture_output=True, text=True, check=True,
    )
    assert (bundle / "index.md").is_file()
    assert (bundle / "log.md").is_file()
    assert (bundle / "sources").is_dir()
    assert (bundle / "sources" / ".gitkeep").is_file()
    # Root index carries the OKF version declaration.
    index_text = (bundle / "index.md").read_text(encoding="utf-8")
    assert "okf_version" in index_text


def test_step_two_ingest_writes_all_concepts(blackbox_bundle):
    """Ingest writes one concept page per source and copies every raw
    source verbatim into ``sources/``.
    """
    bundle, _ = blackbox_bundle
    concepts = sorted((bundle / "concepts").glob("*.md"))
    sources = sorted((bundle / "sources").glob("*.md"))
    assert len(concepts) == 10, (
        f"expected 10 concept pages, got {len(concepts)}: "
        f"{[c.name for c in concepts]}"
    )
    assert len(sources) == 10, (
        f"expected 10 raw sources, got {len(sources)}"
    )
    # Each raw source is byte-identical to the fixture.
    for src in sources:
        fixture = CORPUS / src.name
        assert fixture.exists(), f"source {src.name} has no fixture counterpart"
        assert src.read_bytes() == fixture.read_bytes(), (
            f"sources/{src.name} diverged from fixture"
        )


def test_step_two_ingest_index_lists_every_concept(blackbox_bundle):
    """``index.md`` gains a ``## Sources`` section with one bullet per
    ingested concept — without this, every concept would be an
    orphan."""
    bundle, _ = blackbox_bundle
    text = (bundle / "index.md").read_text(encoding="utf-8")
    assert "## Sources" in text
    for _, slug, _ in EXPECTED_CONCEPTS:
        assert f"concepts/{slug}.md" in text, (
            f"index.md missing entry for {slug}"
        )


def test_step_two_ingest_log_prepends_newest_first(blackbox_bundle):
    """``log.md`` gains 10 ingest entries in newest-first order."""
    bundle, _ = blackbox_bundle
    log_text = (bundle / "log.md").read_text(encoding="utf-8")
    entries = [ln for ln in log_text.splitlines() if ln.startswith("## ")]
    assert len(entries) == 10, (
        f"expected 10 log entries, got {len(entries)}: {entries}"
    )
    # All entries share today's date prefix.
    today_pattern = re.compile(r"^## \d{4}-\d{2}-\d{2} ingest \| ")
    for entry in entries:
        assert today_pattern.match(entry), (
            f"log entry not in '## YYYY-MM-DD ingest | <name>' format: {entry!r}"
        )


def test_step_three_reindex_and_search_finds_each_concept(
    blackbox_bundle, monkeypatch
):
    """``mneme reindex`` followed by ``mneme search <query>`` returns
    the expected concept in the top-3 hits for each domain-specific
    query.

    Uses a deterministic embedder keyed on slug fragments so the test
    is reproducible without downloading the BGE model.

    The init + ingest + lint + dream steps are all subprocess calls
    exercising the CLI surface; reindex and search go through the
    library API because the deterministic embedder is a test-only
    object that can't be injected into a subprocess without adding
    a CLI flag (and that flag would be a 1.0.0 contract leak for a
    test-only concern). ``tests/test_indexlib.py`` and
    ``tests/test_retrieval_bench.py`` follow the same convention.
    """
    bundle, _ = blackbox_bundle

    from mneme import indexlib

    # Build a single Embedder instance reused for reindex + search so
    # dimensions and slug-to-slot mapping stay consistent.
    embedder = indexlib.Embedder(
        NewsKeywordEmbedder().embed,
        model_name="news-blackbox-test",
    )

    result = indexlib.reindex_bundle(str(bundle), embedder)
    assert result.indexed_concepts == 10, (
        f"expected 10 indexed concepts, got {result.indexed_concepts}"
    )

    # Search each domain query and confirm the expected concept
    # appears in the top-3 hits. embed_fn=embedder is the same
    # one used to build the index, so dimensions match.
    for query, expected_slug, _ in EXPECTED_CONCEPTS:
        hits = indexlib.search_bundle(
            str(bundle), query, k=5, embed_fn=embedder,
        )
        assert hits, f"search for {query!r} returned no hits"
        top3 = {h["concept_id"] for h in hits[:3]}
        expected_id = f"concepts/{expected_slug}"
        assert expected_id in top3, (
            f"expected concept {expected_id!r} missing from top-3 for "
            f"{query!r}; got {sorted(top3)}"
        )


def test_step_four_lint_reports_clean_bundle(blackbox_bundle):
    """``mneme lint`` on the ingested bundle reports 0 errors (every
    concept carries valid frontmatter, every link resolves, the log
    is newest-first) and 0 orphans (every concept is reachable from
    ``index.md``). Pre-Task B contract: exit 0 means clean, exit 1
    means OKF errors."""
    bundle, _ = blackbox_bundle
    rc = subprocess.run(
        [sys.executable, "-m", "mneme", "lint", "--bundle", str(bundle)],
        capture_output=True, text=True, check=False,
    )
    assert rc.returncode == 0, (
        f"lint exit code {rc.returncode} (expected 0 = clean):\n"
        f"stdout={rc.stdout}\nstderr={rc.stderr}"
    )
    assert "0 error(s)" in rc.stdout, (
        f"lint reported errors:\n{rc.stdout}"
    )
    assert "orphan concept pages (0)" in rc.stderr, (
        f"lint reported orphans:\n{rc.stderr}"
    )


def test_step_five_dream_subcommand_is_read_only_audit(blackbox_bundle):
    """v2.0 contract: ``mneme dream`` IS a registered read-only audit
    subcommand. There is no ``--apply`` flag (writes happen via the
    SKILL.md workflow after explicit user approval). The CLI never
    shells out to git.
    """
    bundle, _ = blackbox_bundle
    rc = subprocess.run(
        [sys.executable, "-m", "mneme", "dream", "--bundle", str(bundle), "--json"],
        capture_output=True, text=True, check=False,
    )
    assert rc.returncode == 0, (
        f"`mneme dream` should exit 0 (read-only audit); got {rc.returncode}, "
        f"stdout={rc.stdout!r}, stderr={rc.stderr!r}"
    )
    payload = json.loads(rc.stdout)
    assert "none" in payload.get("_meta", {}).get("writes", "")
    # Regression guard: dream must not be implemented as a Python
    # write-path; the audit contract is enforced by the absence of
    # --apply in the parser.
    parser = cli.build_parser()
    dream_sub = parser._subparsers._group_actions[0].choices["dream"]
    option_strings = {flag for action in dream_sub._actions for flag in action.option_strings}
    assert "--apply" not in option_strings
