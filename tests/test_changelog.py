"""Task 9 release-gate — CHANGELOG 2.0.0 / 1.1.0 corrections.

Mneme 2.0.0 is the surface reorientation milestone (dream + search as
the user surface; OKF v0.1 + tags writing discipline; L1 sqlite3 + FTS5
default; L2 deferred to v2.1). Several behaviors changed in ways that
1.1.0's CHANGELOG did not accurately describe (drop lazy install / drop
wheel / drop bilingual SKILL); the 2.0.0 entry must reconcile both.

These tests pin the shape of `## 2.0.0` and the corrected shape of
`## 1.1.0` so a future copy-edit cannot quietly revert either.
"""
from __future__ import annotations

import re
from pathlib import Path
import pytest

pytestmark = pytest.mark.release

ROOT = Path(__file__).resolve().parents[1]
CHANGELOG = ROOT / "CHANGELOG.md"


def _section(text: str, heading: str) -> str:
    """Return the chunk under the first `## <heading>` (until the next `## `)."""
    m = re.search(rf"^##\s+\[?{re.escape(heading)}[^#\n]*$", text, re.MULTILINE)
    if not m:
        return ""
    nxt = re.search(r"^##\s+", text[m.end():], re.MULTILINE)
    end = m.end() + nxt.start() if nxt else len(text)
    return text[m.start():end]


# ---------------------------------------------------------------------------
# ## 2.0.0 — shape assertions
# ---------------------------------------------------------------------------

def test_changelog_has_2_0_0_section() -> None:
    text = CHANGELOG.read_text(encoding="utf-8")
    assert re.search(r"^##\s+\[?2\.0\.0", text, re.MULTILINE), (
        "CHANGELOG.md must have a `## 2.0.0` section"
    )


def test_2_0_0_calls_out_dream_and_search() -> None:
    section = _section(CHANGELOG.read_text(encoding="utf-8"), "2.0.0").lower()
    assert "dream" in section and "search" in section, (
        "`## 2.0.0` must declare `dream` and `search` as the user-facing verbs"
    )


def test_2_0_0_states_l2_defers_to_v2_1() -> None:
    section = _section(CHANGELOG.read_text(encoding="utf-8"), "2.0.0")
    assert "v2.1" in section, (
        "`## 2.0.0` must state that the optional semantic recall layer "
        "(previously L2) defers to v2.1"
    )


def test_2_0_0_documents_breaking_changes() -> None:
    section = _section(CHANGELOG.read_text(encoding="utf-8"), "2.0.0").lower()
    # The "Breaking" cluster covers: dream semantics (read-only audit, no --apply),
    # CLI exit-code changes (`init` rc=1 overwriting vs idempotent, `lint` exit
    # code 0/1 replacing the LINT_GUARD_RC=3 signal), and the L2 removal.
    markers = (
        "breaking",
        "rc=1",
        "lint exit code",
        "exit code 0",
        "l1 default",
        "l2",
    )
    hits = [m for m in markers if m in section]
    assert hits, (
        "`## 2.0.0` must include a Breaking cluster — at least one of: "
        f"{markers!r}. Found none."
    )


def test_2_0_0_no_lazy_install_claim() -> None:
    """The 2.0.0 entry must not advertise an auto-install / lazy-install feature."""
    section = _section(CHANGELOG.read_text(encoding="utf-8"), "2.0.0").lower()
    bad = ("lazy install", "auto-install", "ensure_index_deps")
    leaks = [b for b in bad if b in section]
    assert not leaks, (
        f"`## 2.0.0` still advertises a lazy-install behavior {leaks!r}; "
        "v2.0 has no auto-install path. Any first-time L2 install note must "
        "be in the 'L2 deferred to v2.1' subsection, not the main features."
    )


def test_2_0_0_records_drop_of_naive_rag_framing() -> None:
    section = _section(CHANGELOG.read_text(encoding="utf-8"), "2.0.0").lower()
    assert "naive" in section or "rag" in section, (
        "`## 2.0.0` must call out the explicit removal of the Naive-RAG framing"
    )


# ---------------------------------------------------------------------------
# ## 1.1.0 — corrected state
# ---------------------------------------------------------------------------

def test_1_1_0_is_corrected_in_2_0_0() -> None:
    section = _section(CHANGELOG.read_text(encoding="utf-8"), "1.1.0").lower()
    assert re.search(r"corrected|reverted|drop", section), (
        "`## 1.1.0` should be marked as corrected/reverted (drop lazy install / "
        "drop wheel / drop bilingual SKILL) so a reader does not mistake the "
        "old description for 2.0 truth."
    )


def test_readme_2_0_version_is_topmost_released() -> None:
    """`## 2.0.0` should appear above `## 1.1.0` in source order."""
    text = CHANGELOG.read_text(encoding="utf-8")
    a = re.search(r"^##\s+\[?2\.0\.0", text, re.MULTILINE)
    b = re.search(r"^##\s+\[?1\.1\.0", text, re.MULTILINE)
    assert a and b, "expected both `## 2.0.0` and `## 1.1.0` sections"
    assert a.start() < b.start(), (
        "`## 2.0.0` must precede `## 1.1.0` in CHANGELOG.md (newest first)."
    )
