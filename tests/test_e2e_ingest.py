"""End-to-end ingest harness (Phase 3 / 0.4.0 milestone).

The host agent is supposed to follow the SKILL.md §"Scenario: ingest"
steps when given a source:

  0. preserve the raw source as `<bundle>/raw-sources/<basename>.raw`
     and create an OKF Source page under `<bundle>/sources/`
  1. read the source
  2. decompose into concept pages (one per atomic idea)
  3. write each page to `<bundle>/concepts/<slug>.md`
  4. edit `<bundle>/index.md` (append under a ## section heading)
  5. edit `<bundle>/log.md` — **prepend** (insert at top) the new entry
  6. run `mneme reindex`
  7. (search / lint as follow-up)

This module scripts those steps for a small fixture source
(`tests/fixtures/e2e_ingest/source.md`) and asserts each contract
the freeze-v0.2.1rc1 ingest rules pinned down. The LLM steps
(decompose, write the body of each concept page) are pre-baked into a
single hardcoded distillation here — the point of the harness is
that the deterministic shell around the LLM stays correct: copy,
prepend, cross-link, reindex.

If any of these tests fail, the host agent is supposed to break.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest
# v1.1.0 switched CLI entry from `mneme <cmd>` console command to
# `python3 ~/.claude/skills/mneme/scripts/mneme.py <cmd>`. These
# subprocess tests still call the old form and need a rewrite
# (PR2 / PR3 work). Default-skipped per pyproject.toml addopts.
pytestmark = [pytest.mark.e2e, pytest.mark.compat]

from mneme import indexlib
from mneme.indexlib import Embedder


ROOT = Path(__file__).parent.parent
FIXTURE_SOURCE = ROOT / "tests" / "fixtures" / "e2e_ingest" / "source.md"


# ─────────────────────────────────────────────────────────────────────────────
# A scripted ingest distillation. In production the LLM does this; here
# we hardcode one well-formed decomposition so the harness exercises the
# deterministic shell.
# ─────────────────────────────────────────────────────────────────────────────

def scripted_distillation(source_text: str) -> list[dict]:
    """Return the pre-baked decomposition of `source_text`.

    Each entry is a dict with keys: title, slug, type, body, tags.
    """
    return [
        {
            "title": "OKF v0.1 — Quick Summary",
            "slug": "okf-quick-summary",
            "type": "Concept",
            "tags": ["okf", "format"],
            "body": (
                "OKF (Open Knowledge Format) is a directory-of-Markdown "
                "format for representing linked concept pages.\n\n"
                "See also: [/concepts/okf-frontmatter.md]"
                "(/concepts/okf-frontmatter.md), "
                "[/concepts/okf-cross-refs.md](/concepts/okf-cross-refs.md).\n"
            ),
        },
        {
            "title": "OKF v0.1 — Frontmatter",
            "slug": "okf-frontmatter",
            "type": "Reference",
            "tags": ["okf", "frontmatter"],
            "body": (
                "Every non-reserved `.md` file in an OKF bundle MUST "
                "have a `---`-delimited YAML frontmatter block. The block "
                "MUST declare a non-empty `type` field with one of "
                "`Concept` / `Reference` / `Summary` / `Source`.\n"
            ),
        },
        {
            "title": "OKF v0.1 — Cross-references",
            "slug": "okf-cross-refs",
            "type": "Concept",
            "tags": ["okf", "links"],
            "body": (
                "OKF cross-references use absolute bundle-relative "
                "paths (`/concepts/<slug>.md`) so a file move does not "
                "break a reference to it.\n"
            ),
        },
    ]


# ─────────────────────────────────────────────────────────────────────────────
# A scripted ingest runner: each step is what the SKILL.md tells the
# host agent to do. Failures here mean the agent instructions are wrong.
# ─────────────────────────────────────────────────────────────────────────────

def scripted_ingest(bundle: Path, source: Path) -> None:
    """Run the SKILL.md ingest steps against an existing empty bundle.

    The bundle must already be initialized (`mneme init`).
    The source is what the host agent is asked to distill.
    """
    bundle = Path(bundle)
    source = Path(source)

    # Step 0: preserve raw bytes outside the OKF Markdown namespace and
    # create a Source page that points to the artifact.
    raw_sources_dir = bundle / "raw-sources"
    raw_sources_dir.mkdir(exist_ok=True)
    raw_dest = raw_sources_dir / f"{source.name}.raw"
    if raw_dest.exists() and raw_dest.read_bytes() != source.read_bytes():
        raise RuntimeError(
            f"raw-sources/{source.name}.raw exists with different content; "
            "abort and ask the user."
        )
    shutil.copy(source, raw_dest)

    sources_dir = bundle / "sources"
    sources_dir.mkdir(exist_ok=True)
    source_page = sources_dir / source.name
    source_page.write_text(
        "---\n"
        "type: Source\n"
        "title: OKF fixture source\n"
        "description: Provenance page for the end-to-end ingest fixture.\n"
        "tags: [source, fixture]\n"
        "timestamp: 2026-07-12T10:00:00Z\n"
        f"resource: /raw-sources/{source.name}.raw\n"
        "---\n\n"
        "Immutable fixture artifact referenced by this OKF Source page.\n",
        encoding="utf-8",
    )

    # Step 1-3: read + decompose + write concept pages.
    text = source.read_text(encoding="utf-8")
    pages = scripted_distillation(text)
    concepts_dir = bundle / "concepts"
    concepts_dir.mkdir(exist_ok=True)
    for page in pages:
        page_path = concepts_dir / f"{page['slug']}.md"
        page_path.write_text(
            "---\n"
            f"type: {page['type']}\n"
            f"title: {page['title']}\n"
            f"description: auto-generated distillation of {source.name}\n"
            f"tags: [{', '.join(page['tags'])}]\n"
            f"timestamp: 2026-07-12T10:00:00Z\n"
            f"resource: /sources/{source.name}\n"
            "---\n\n"
            f"{page['body']}\n",
            encoding="utf-8",
        )

    # Step 4: edit index.md under a ## Concepts section
    index_path = bundle / "index.md"
    lines = index_path.read_text(encoding="utf-8").splitlines()
    if "## Concepts" not in lines:
        lines.append("## Concepts")
        lines.extend(
            f"* [{p['title']}](concepts/{p['slug']}.md) — {p['title']}."
            for p in pages
        )
    else:
        # Append under existing section.
        i = lines.index("## Concepts")
        while i + 1 < len(lines) and lines[i + 1].startswith("## "):
            i += 1
        for p in reversed(pages):
            lines.insert(
                i + 1,
                f"* [{p['title']}](concepts/{p['slug']}.md) — {p['title']}.",
            )
    if "## Sources" not in lines:
        lines.extend(
            [
                "## Sources",
                f"* [Fixture source](sources/{source.name}) — immutable provenance.",
            ]
        )
    index_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Step 5: prepend to log.md
    log_path = bundle / "log.md"
    existing = log_path.read_text(encoding="utf-8") if log_path.exists() else "# Directory Update Log\n"
    new_entry = (
        f"## 2026-07-12 ingest | {source.name}\n\n"
        f"Distilled into {len(pages)} concept pages.\n"
    )
    # Prepend: new entry goes between the H1 and any existing entries.
    lines = existing.splitlines()
    if lines and lines[0].startswith("# ") and not lines[0].startswith("## "):
        head = [lines[0]]
        rest = lines[1:]
    else:
        head = ["# Directory Update Log"]
        rest = lines
    log_path.write_text(
        "\n".join(head + [new_entry.rstrip("\n"), ""] + rest) + "\n",
        encoding="utf-8",
    )


# ─────────────────────────────────────────────────────────────────────────────
# An embedder with one fixed concept per distilled page, so search is
# deterministic across reindex runs.
# ─────────────────────────────────────────────────────────────────────────────

class DeterministicEmbedder(Embedder):
    """Returns a one-hot vector identifying the page by index in the source."""

    def __init__(self, n_concepts: int):
        self.n = n_concepts

    def embed(self, texts):
        # Return 4-dim vectors; non-concepts get an "absent" vector.
        # The exact mapping is brittle but stable: chunk i -> vector with
        # 1.0 at slot i.
        out = []
        for t in texts:
            v = [0.0] * self.n
            # Map chunk text back to a slot. We embed only the first page
            # of each known slug; otherwise return a zero vector.
            for i, slug in enumerate([
                "okf-quick-summary",
                "okf-frontmatter",
                "okf-cross-refs",
            ]):
                if slug in t:
                    v[i] = 1.0
                    break
            else:
                v[0] = 0.5  # mild similarity to the summary
            out.append(v)
        return out


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_step_zero_preserves_raw_source_and_creates_okf_source_page(tmp_path):
    bundle = tmp_path / "wiki"
    cfg = tmp_path / "cfg.toml"
    rc = subprocess.run(
        [sys.executable, "-m", "mneme", "init", str(bundle),
         "--config", str(cfg)],
        check=True, capture_output=True, text=True,
    )
    assert (bundle / "sources").is_dir()
    scripted_ingest(bundle, FIXTURE_SOURCE)
    raw = bundle / "raw-sources" / "source.md.raw"
    assert raw.is_file()
    assert raw.read_bytes() == FIXTURE_SOURCE.read_bytes()
    source_page = bundle / "sources" / "source.md"
    assert "type: Source" in source_page.read_text(encoding="utf-8")
    assert "resource: /raw-sources/source.md.raw" in source_page.read_text(encoding="utf-8")


def test_step_three_concept_pages_carry_type(tmp_path):
    """Each distilled concept page MUST have a non-empty scalar `type`
    (PR2 §4.1 + OKF §4.1)."""
    bundle = tmp_path / "wiki"
    cfg = tmp_path / "cfg.toml"
    subprocess.run(
        [sys.executable, "-m", "mneme", "init", str(bundle),
         "--config", str(cfg)],
        check=True, capture_output=True,
    )
    scripted_ingest(bundle, FIXTURE_SOURCE)
    for page in scripted_distillation(FIXTURE_SOURCE.read_text()):
        path = bundle / "concepts" / f"{page['slug']}.md"
        assert path.is_file(), f"missing concept page: {path}"
        text = path.read_text(encoding="utf-8")
        # type: <Name> scalar — must be a string, not a list / int / etc.
        assert f"\ntype: {page['type']}\n" in text, (
            f"concept {path.name} missing type field"
        )


def test_step_five_log_prepends_newest_first(tmp_path):
    """§3.7 + §7 log: ingest must prepend, not append."""
    bundle = tmp_path / "wiki"
    cfg = tmp_path / "cfg.toml"
    subprocess.run(
        [sys.executable, "-m", "mneme", "init", str(bundle),
         "--config", str(cfg)],
        check=True, capture_output=True,
    )
    scripted_ingest(bundle, FIXTURE_SOURCE)
    log_text = (bundle / "log.md").read_text(encoding="utf-8")
    lines = [ln for ln in log_text.splitlines() if ln.startswith("## ")]
    assert len(lines) >= 1
    # The most recent entry must be the ingest we just did.
    assert "2026-07-12 ingest | source.md" in lines[0], (
        f"newest log entry is not the prepended ingest: {lines[0]!r}"
    )


def test_step_four_index_links_each_concept(tmp_path):
    """§3.6 step 4: index.md must list each concept page under ## Concepts."""
    bundle = tmp_path / "wiki"
    cfg = tmp_path / "cfg.toml"
    subprocess.run(
        [sys.executable, "-m", "mneme", "init", str(bundle),
         "--config", str(cfg)],
        check=True, capture_output=True,
    )
    scripted_ingest(bundle, FIXTURE_SOURCE)
    text = (bundle / "index.md").read_text(encoding="utf-8")
    assert "## Concepts" in text
    for page in scripted_distillation(FIXTURE_SOURCE.read_text()):
        assert f"concepts/{page['slug']}.md" in text, (
            f"index.md missing entry for {page['slug']}"
        )


@pytest.mark.network
def test_step_six_reindex_then_step_seven_search_finds_each_concept(
    tmp_path, monkeypatch
):
    """End-to-end: ingest → reindex (deterministic embedder) → search
    finds every concept page. Locks in the user-facing flow that the
    host agent can follow reproducibly.
    """
    bundle = tmp_path / "wiki"
    cfg = tmp_path / "cfg.toml"
    subprocess.run(
        [sys.executable, "-m", "mneme", "init", str(bundle),
         "--config", str(cfg)],
        check=True, capture_output=True,
    )
    scripted_ingest(bundle, FIXTURE_SOURCE)

    pages = scripted_distillation(FIXTURE_SOURCE.read_text())
    pages_concepts = pages  # each distilled entry becomes one concept
    n = len(pages_concepts)

    # Deterministic embedder so search ordering is reproducible.
    monkeypatch.setattr(indexlib, "default_embed_fn",
                        lambda: DeterministicEmbedder(n))

    rc = subprocess.run(
        [sys.executable, "-m", "mneme", "reindex",
         "--config", str(cfg)],
        capture_output=True, text=True, check=False,
    )
    assert rc.returncode == 0, rc.stderr
    assert "indexed" in rc.stdout

    # Search for each concept and confirm the top hit is its page.
    for page in pages_concepts:
        rc = subprocess.run(
            [sys.executable, "-m", "mneme", "search", page["slug"],
             "-k", "5", "--json", "--config", str(cfg)],
            capture_output=True, text=True, check=False,
        )
        assert rc.returncode == 0, rc.stderr
        hits = __import__("json").loads(rc.stdout)
        assert hits, f"no search hits for query {page['slug']!r}"
        assert any(
            hit.get("concept_id") == f"concepts/{page['slug']}" for hit in hits
        ), (
            f"top hits for {page['slug']!r} don't include the expected "
            f"concept_id: {hits}"
        )


def test_e2e_lint_clean_after_ingest(tmp_path):
    """After scripted ingest + reindex, `mneme lint` reports the bundle
    as clean (the find_orphans guard still fires; that's the only
    expected non-zero report).
    """
    bundle = tmp_path / "wiki"
    cfg = tmp_path / "cfg.toml"
    subprocess.run(
        [sys.executable, "-m", "mneme", "init", str(bundle),
         "--config", str(cfg)],
        check=True, capture_output=True,
    )
    scripted_ingest(bundle, FIXTURE_SOURCE)
    rc = subprocess.run(
        [sys.executable, "-m", "mneme", "lint", str(bundle)],
        capture_output=True, text=True, check=False,
    )
    assert "0 error(s)" in rc.stdout, rc.stdout
    # v0.6.1: lint always emits an orphan section (empty if none).
    assert "orphan concept pages" in rc.stderr
    # Regression guard: the v0.3.0 freeze guard message must not
    # come back — find_orphans IS implemented.
    assert "find_orphans not yet implemented" not in rc.stderr
