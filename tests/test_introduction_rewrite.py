"""Release-gate — Mneme 4.2 public surface.

The README and introduction must describe the four-verb surface —
mneme (记) / dream (整理) / search (读) / serve (看) — and the v4.2
`mneme serve` localhost console (with its three real screenshots),
plus both release downloads. The deep-dive sections (Graph internals,
nightly-task boundary) were deliberately cut from the landing page in
favour of a shorter marketing read; their gates live elsewhere.

The introduction page must expose `npx skills add Scott1743/mneme` as
the install CTA; the README must be self-contained about the four-layer
architecture (raw / wiki / skill / disposable accelerator) and clearly
state L2 defers to v2.1.
"""
from __future__ import annotations

import re
from pathlib import Path
import pytest

pytestmark = pytest.mark.release

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
INTRO = ROOT / "introduction" / "index.html"

USER_FACING_TARGETS = (README, INTRO)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@pytest.mark.parametrize("path", USER_FACING_TARGETS, ids=lambda p: p.name)
def test_release_downloads_are_present(path: Path) -> None:
    text = _read(path)
    assert "releases/download/v2.2.0/mneme-2.2.0.zip" in text
    assert "releases/download/v4.1.0/mneme-4.1.0.zip" in text


def test_introduction_install_command_present() -> None:
    text = _read(INTRO)
    assert "npx skills add Scott1743/mneme" in text, (
        "introduction page must surface the skill.sh install one-liner as the CTA"
    )


def test_introduction_has_dream_and_search() -> None:
    text = _read(INTRO).lower()
    assert "dream" in text, "introduction page must mention `dream` as a user verb"
    assert "search" in text, "introduction page must mention `search` as a user verb"


def test_introduction_tagline_has_four_verbs() -> None:
    """v4.2 narrative frame: mneme 记 / dream 整理 / search 读 / serve 看."""
    text = _read(INTRO)
    m = re.search(r'<p class="tagline">(.*?)</p>', text, re.S)
    assert m, "hero tagline is missing"
    tagline = m.group(1)
    for verb in ("mneme", "dream", "search", "serve"):
        assert verb in tagline, f"tagline must weave in {verb!r}: {tagline!r}"
    assert "dream 写，search 读" not in text, (
        "the old two-verb framing 'dream 写，search 读' must be gone"
    )


def test_introduction_serve_section_is_marketing_voice() -> None:
    """The §V console section keeps the user-approved short marketing copy."""
    text = _read(INTRO)
    assert "开了一扇窗" in text
    assert "复制提示词" in text
    assert "就当它没来过" in text
    assert "serve</span> 是这一切的那扇窗" in text


def test_readme_surfaces_dream_and_search() -> None:
    text = _read(README).lower()
    assert "dream" in text and "search" in text, (
        "README must show dream + search as the user surface"
    )


def test_readme_states_v4_graph_option() -> None:
    text = _read(README)
    assert "v4" in text and "reindex --graph" in text and "--mode hybrid" in text


def test_introduction_states_current_release() -> None:
    text = _read(INTRO)
    assert "<title>Mneme · 记忆女神 · v4.3</title>" in text
    assert "v4.3" in text
    assert "Mneme 2.1" not in text
    assert "两个动词" not in text
    assert "其余都是细节" not in text


def test_introduction_surfaces_v42_serve_console() -> None:
    """v4.2 ships the `mneme serve` localhost console; the page shows it
    with three real screenshots stored under introduction/assets/ (the
    one sanctioned exception to the self-contained rule, user-approved)."""
    text = _read(INTRO)
    assert "mneme serve" in text
    for name in ("serve-overview", "serve-lint", "serve-browse"):
        rel = f"assets/{name}.png"
        assert rel in text, f"introduction page must embed {rel}"
        assert (INTRO.parent / rel).is_file(), f"missing screenshot {rel}"


def test_introduction_uses_absolute_bundle_relative_citations() -> None:
    text = _read(INTRO)
    assert "以 <code>/</code> 开头的 bundle-relative 路径" in text


def test_introduction_no_naive_rag() -> None:
    text = _read(INTRO).lower()
    assert "naive rag" not in text, (
        "introduction page must not frame Mneme as 'Naive RAG'; the 2.0 thesis "
        "is compile-once / walk-the-graph, not embed-then-KNN."
    )
