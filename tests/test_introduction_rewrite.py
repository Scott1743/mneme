"""Task 9 release-gate — Mneme 2.0 surface rewrite (dream + search).

The 2.0 README + introduction are the user-facing face of the surface
reorientation: `dream` + `search` only, no L2 path, no Naive-RAG framing,
no `--l2` / `sqlite-vec` / `fastembed` / `BGE` / `auto-install` anywhere.

The introduction page must expose `npx skills add Scott1743/mneme` as
the install CTA; the README must be self-contained about the four-layer
architecture (raw / wiki / skill / disposable accelerator) and clearly
state L2 defers to v2.1.
"""
from __future__ import annotations

from pathlib import Path
import pytest

pytestmark = pytest.mark.release

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
INTRO = ROOT / "introduction" / "index.html"

# 2.0 surface messaging — these tokens are forbidden anywhere in the
# user-facing rewrite (per docs/superpowers/specs/2026-07-13-mneme-2.0-design.md).
FORBIDDEN_TOKENS = (
    "--l2",
    "sqlite-vec",
    "fastembed",
    "bge",
    "naive rag",
    "auto-install",
)

USER_FACING_TARGETS = (README, INTRO)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "path", USER_FACING_TARGETS, ids=lambda p: p.name
)
def test_no_l2_or_rag_messaging(path: Path) -> None:
    text = _read(path).lower()
    for token in FORBIDDEN_TOKENS:
        assert token not in text, (
            f"{path.name} must not contain 2.0-forbidden token {token!r}. "
            "L2 defers to v2.1; the user surface is dream + search."
        )


def test_introduction_install_command_present() -> None:
    text = _read(INTRO)
    assert "npx skills add Scott1743/mneme" in text, (
        "introduction page must surface the skill.sh install one-liner as the CTA"
    )


def test_introduction_has_dream_and_search() -> None:
    text = _read(INTRO).lower()
    assert "dream" in text, "introduction page must mention `dream` as a user verb"
    assert "search" in text, "introduction page must mention `search` as a user verb"


def test_readme_surfaces_dream_and_search() -> None:
    text = _read(README).lower()
    assert "dream" in text and "search" in text, (
        "README must show dream + search as the user surface"
    )


def test_readme_states_v2_is_zero_dependency() -> None:
    text = _read(README)
    assert "v2.0 不含语义召回" in text


def test_introduction_links_both_release_assets() -> None:
    text = _read(INTRO)
    assert "releases/download/v2.0.0/mneme-2.0.0.zip" in text
    assert "releases/download/v3.0.0/mneme-3.0.0.zip" in text


def test_introduction_no_naive_rag() -> None:
    text = _read(INTRO).lower()
    assert "naive rag" not in text, (
        "introduction page must not frame Mneme as 'Naive RAG'; the 2.0 thesis "
        "is compile-once / walk-the-graph, not embed-then-KNN."
    )
