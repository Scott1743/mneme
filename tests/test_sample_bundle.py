# Sample-bundle contract tests for the v2.0 OKF + tags protocol.
#
# Steps mapped to Task 8 of docs/superpowers/plans/2026-07-13-mneme-2.0-implementation.md
#  * raw content lives outside the bundle (sample-bundle/external-sources/)
#  * sample-bundle/sources/ contains only OKF Source pointer pages
#  * every Mneme-written concept page carries >=1 tag (writer rule)
#  * topics/llm-wiki.md aggregates the related concepts
#  * index.md lists all aggregation paths
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

BUNDLE = Path(__file__).resolve().parent.parent / "sample-bundle"


def test_no_raw_source_md_inside_bundle():
    """Raw source content must live OUTSIDE the bundle. `sources/` may
    contain only OKF `Source` pointer pages (with frontmatter). True raw
    excerpts live in `external-sources/`.
    """
    raw = []
    for p in BUNDLE.rglob("sources/*.md"):
        text = p.read_text(encoding="utf-8")
        if not text.lstrip().startswith("---"):
            raw.append(p)
    assert not raw, (
        "raw content must live outside the bundle, in external-sources/: "
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


def test_external_sources_immutable():
    """external-sources/ holds raw content with NO frontmatter (immutable inputs)."""
    external = BUNDLE / "external-sources"
    assert external.exists(), "external-sources/ directory missing"
    md_files = list(external.rglob("*.md"))
    assert md_files, "external-sources/ must contain raw content"
    for p in md_files:
        text = p.read_text(encoding="utf-8")
        assert not text.lstrip().startswith("---"), (
            f"{p}: raw content in external-sources/ must have NO frontmatter"
        )


def test_source_pointer_points_to_external_raw():
    """The OKF Source pointer page declares a `resource:` field that
    resolves to a real file under external-sources/.
    """
    p = BUNDLE / "sources" / "karpathy-llm-wiki.md"
    assert p.exists(), "sources/karpathy-llm-wiki.md (Source pointer) missing"
    text = p.read_text(encoding="utf-8")
    assert "type: Source" in text, f"{p}: missing `type: Source` frontmatter"
    assert "resource:" in text, f"{p}: missing `resource:` pointer"
    # The resource points to external-sources/<name>.md.
    m = re.search(r"resource:\s*(\S+)", text)
    assert m, f"{p}: resource URI not parseable"
    target = m.group(1).replace("file:///", "").lstrip("/")
    target_path = (BUNDLE / target).resolve()
    assert target_path.exists(), f"{p}: resource target {target} not found"
