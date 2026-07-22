# Sample-bundle contract tests for the v2.0 OKF + tags protocol.
#
# Steps mapped to Task 8 of docs/superpowers/plans/2026-07-13-mneme-2.0-implementation.md
#  * raw content uses opaque artifacts under sample-bundle/raw-sources/
#  * sample-bundle/sources/ contains only OKF Source pages
#  * every Mneme-written concept page carries >=1 tag (writer rule)
#  * topics/llm-wiki.md aggregates the related concepts
#  * index.md lists all aggregation paths
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

BUNDLE = Path(__file__).resolve().parent.parent / "sample-bundle"


def test_sources_contains_only_okf_pages():
    """Every Markdown file in `sources/` is an OKF Source page."""
    raw = []
    for p in BUNDLE.rglob("sources/*.md"):
        text = p.read_text(encoding="utf-8")
        if not text.lstrip().startswith("---"):
            raw.append(p)
    assert not raw, (
        "sources/ contains raw Markdown instead of OKF Source pages: "
        f"{raw}"
    )


def test_sample_bundle_lints_clean():
    """The sample bundle passes the OKF validator with zero ERRORs.

    We use the `validate_bundle` API directly so the assertion is about
    ERROR diagnostics, not CLI exit-code semantics (which are tuned for
    a slightly different release).
    """
    from mneme import okflib

    report = okflib.validate_bundle(BUNDLE)
    errors = [(v.path, v.rule, v.detail) for v in report.errors]
    assert not errors, f"unexpected lint errors: {errors}"


def test_concept_pages_have_tags():
    """Every Mneme-written concept page declares >=1 tag (writer rule)."""
    for p in sorted((BUNDLE / "concepts").glob("*.md")):
        text = p.read_text(encoding="utf-8")
        m = re.match(r"\A---[ \t]*\n(.*?)\n---[ \t]*\n?", text, re.S)
        assert m, f"{p}: missing frontmatter block"
        fm = m.group(1)
        assert "tags:" in fm, f"{p}: missing tags in frontmatter block"
        tail = fm.split("tags:", 1)[1].splitlines()[0].strip()
        assert tail.startswith("["), f"{p}: tags must be a list, got {tail!r}"
        inner = tail.strip("[]").strip()
        assert inner and inner != ",", f"{p}: tags list is empty"


def test_topic_page_links_concepts():
    """topics/llm-wiki.md must aggregate the two root concepts."""
    tp = (BUNDLE / "topics" / "llm-wiki.md").read_text(encoding="utf-8")
    assert "/concepts/llm-wiki.md" in tp
    assert "/concepts/okf.md" in tp


def test_index_lists_aggregation_paths():
    """index.md must list concepts, topics, and sources paths."""
    text = (BUNDLE / "index.md").read_text(encoding="utf-8")
    assert "/concepts/llm-wiki.md" in text
    assert "/concepts/okf.md" in text
    assert "/topics/llm-wiki.md" in text
    assert "/sources/karpathy-llm-wiki.md" in text


def test_raw_sources_are_opaque_immutable_artifacts():
    """Markdown originals use `.md.raw`, outside OKF's `.md` namespace."""
    raw_dir = BUNDLE / "raw-sources"
    assert raw_dir.exists(), "raw-sources/ directory missing"
    artifacts = list(raw_dir.rglob("*.md.raw"))
    assert artifacts, "raw-sources/ must contain a Markdown raw artifact"
    assert not list(raw_dir.rglob("*.md")), "raw Markdown must not end in .md"
    for path in artifacts:
        assert not path.read_text(encoding="utf-8").lstrip().startswith("---")


def test_source_pointer_points_to_external_raw():
    """The OKF Source pointer page declares a `resource:` field that
    resolves to a real opaque artifact under raw-sources/.
    """
    p = BUNDLE / "sources" / "karpathy-llm-wiki.md"
    assert p.exists(), "sources/karpathy-llm-wiki.md (Source pointer) missing"
    text = p.read_text(encoding="utf-8")
    assert "type: Source" in text, f"{p}: missing `type: Source` frontmatter"
    assert "resource:" in text, f"{p}: missing `resource:` pointer"
    # The resource points to raw-sources/<name>.md.raw.
    m = re.search(r"resource:\s*(\S+)", text)
    assert m, f"{p}: resource URI not parseable"
    target = m.group(1).lstrip("/")
    target_path = (BUNDLE / target).resolve()
    assert target_path.exists(), f"{p}: resource target {target} not found"
