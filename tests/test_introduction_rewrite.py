"""Release-gate — Mneme 4.0 public surface.

The README and introduction must describe the `dream` + `search` surface,
the explicit v4 Graph + hybrid retrieval option, and both release downloads.

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
    assert "v4.0" in text


def test_introduction_no_naive_rag() -> None:
    text = _read(INTRO).lower()
    assert "naive rag" not in text, (
        "introduction page must not frame Mneme as 'Naive RAG'; the 2.0 thesis "
        "is compile-once / walk-the-graph, not embed-then-KNN."
    )
