"""Release-gate for the `introduction/` GitHub Pages landing page.

The Mneme introduction page is published via `.github/workflows/pages.yml`
to https://scott1743.github.io/mneme/introduction/. Failing one of these
assertions means the page is broken, or it has drifted from its intended
three-section structure and Forest cross-promo envelope.

gstack plan-eng-review (round 1) flagged the original 5-string smoke test
as too light for a release gate; this file implements the upgraded
structural + anchor + link assertions recommended by the review.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

import pytest

pytestmark = pytest.mark.release

ROOT = Path(__file__).resolve().parents[1]
INTRO_HTML = ROOT / "introduction" / "index.html"

REQUIRED_SECTION_IDS = ("初衷", "安装", "面板", "朋友")

CANONICAL_FOREST_URLS = (
    "https://github.com/Scott1743/tarot-confessional",
    "https://scott1743.github.io/tarot-confessional/",
)
MNEME_REPO_URL = "https://github.com/Scott1743/mneme"
SKILLS_INSTALL_CMD = "npx skills add Scott1743/mneme"

# CLAUDE.md §"网络受限环境" — page must not pull anything from third-party CDNs.
FORBIDDEN_DOMAIN_SUBSTRINGS = ("cdn.", "googleapis.", "fonts.")
# Don't expose unreleased branch names of the sibling project.
FORBIDDEN_BRANCH = "codex/forest-whispers-ui"


# ---------------------------------------------------------------------------
# Parser helpers (stdlib-only; avoid BeautifulSoup/lxml dependency creep).
# ---------------------------------------------------------------------------

class _PageParser(HTMLParser):
    """Collects the structural facts we need from the introduction page."""

    def __init__(self) -> None:
        super().__init__()
        self.h1_count = 0
        self.section_ids: list[str] = []
        self.nav_anchors: list[str] = []
        self._in_nav = False

    def handle_starttag(self, tag: str, attrs):
        attrs_d = dict(attrs)
        if tag == "h1":
            self.h1_count += 1
        elif tag == "section" and "id" in attrs_d:
            self.section_ids.append(attrs_d["id"])
        elif tag == "nav":
            self._in_nav = True
        elif tag == "a" and self._in_nav:
            href = attrs_d.get("href", "")
            if href.startswith("#"):
                self.nav_anchors.append(href.lstrip("#"))

    def handle_endtag(self, tag: str):
        if tag == "nav":
            self._in_nav = False


def _read_page() -> tuple[str, _PageParser]:
    text = INTRO_HTML.read_text(encoding="utf-8")
    parser = _PageParser()
    parser.feed(text)
    return text, parser


# ---------------------------------------------------------------------------
# Structural assertions
# ---------------------------------------------------------------------------

def test_introduction_html_exists():
    """The introduction page must exist at the expected path."""
    assert INTRO_HTML.is_file(), (
        f"{INTRO_HTML} missing; the GitHub Pages deploy workflow depends on it."
    )


def test_single_h1():
    """The page exposes exactly one top-level <h1>."""
    _, parser = _read_page()
    assert parser.h1_count == 1, (
        f"expected exactly one <h1> on the introduction page; got {parser.h1_count}"
    )


def test_landing_sections_present():
    """The page exposes its four <section id=...> elements: thesis, install,
    serve console, friends. (The deep-dive 原理/为什么 sections were cut in
    v4.2 to keep the landing page a short marketing read.)"""
    _, parser = _read_page()
    missing = [sid for sid in REQUIRED_SECTION_IDS if sid not in parser.section_ids]
    assert not missing, (
        f"<section id=\"...\"> missing for: {missing}; "
        f"present section ids: {parser.section_ids}"
    )


def test_nav_anchors_resolve():
    """Every <a href=\"#...\"> inside <nav> points to an id that exists on the page."""
    text, parser = _read_page()
    assert parser.nav_anchors, "no <a href=\"#...\"> entries found inside <nav>"
    page_ids = set(re.findall(r'id="([^"]+)"', text))
    unresolved = [a for a in parser.nav_anchors if a not in page_ids]
    assert not unresolved, (
        f"<nav> anchors point to missing ids: {unresolved}; "
        f"available ids: {sorted(page_ids)}"
    )


# ---------------------------------------------------------------------------
# Content / cross-link assertions
# ---------------------------------------------------------------------------

def test_forest_promo_uses_canonical_urls():
    """The Forest cross-promo only ever uses canonical URLs (not dev branches)."""
    text, _ = _read_page()
    for url in CANONICAL_FOREST_URLS:
        assert url in text, (
            f"introduction page must link to canonical Forest URL {url!r} "
            f"in the § 1 初衷 / 朋友项目 block."
        )


def test_mneme_install_command_present():
    """The skill.sh install one-liner is on the page."""
    text, _ = _read_page()
    assert SKILLS_INSTALL_CMD in text, (
        f"introduction page must show the skill.sh install command "
        f"({SKILLS_INSTALL_CMD!r})."
    )
    assert MNEME_REPO_URL in text, (
        f"introduction page must link to the canonical Mneme repo URL {MNEME_REPO_URL!r}."
    )


def test_does_not_promote_unreleased_branch():
    """Never reference the sibling project's unreleased branch name publicly."""
    text, _ = _read_page()
    assert FORBIDDEN_BRANCH not in text, (
        f"introduction page references unreleased branch {FORBIDDEN_BRANCH!r}; "
        f"only canonical tarot-confessional URLs are allowed."
    )


# ---------------------------------------------------------------------------
# Style / external-resource guards
# ---------------------------------------------------------------------------

def test_no_external_cdn_references():
    """No third-party CDN / font-house / googleapis references anywhere."""
    text, _ = _read_page()
    hits = [d for d in FORBIDDEN_DOMAIN_SUBSTRINGS if d in text]
    assert not hits, (
        f"forbidden CDN/family reference(s) in introduction page: {hits}; "
        f"CLAUDE.md flags the host as network-restricted."
    )


def test_inline_style_has_no_external_refs():
    """The single <style> block has no @import / src= / url() pointing outside."""
    text, _ = _read_page()
    blocks = re.findall(r"<style[^>]*>(.*?)</style>", text, flags=re.S)
    assert blocks, "no <style> block found; the introduction page must inline its CSS"
    bad = re.findall(r"@import|\bsrc\s*=|url\(\s*['\"]?https?:", "\n".join(blocks))
    assert not bad, (
        f"inline <style> has forbidden external refs: {bad}; "
        f"the page must be self-contained."
    )
