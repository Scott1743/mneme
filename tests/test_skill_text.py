"""Phase 0 freeze §3.2 / §3.6 / §3.7 — text-level guards on SKILL.md and
workflow-ingest.md. Each test asserts a missing doc directive that must be
fixed before PR1 lands.

v1.1.0 dropped the bilingual SKILL cn.md variant; the SKILL text contract
is now a single English file.
"""
import re
from pathlib import Path
import pytest
pytestmark = pytest.mark.docs

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "mneme"
SKILL_MD = SKILL_DIR / "SKILL.md"
WORKFLOW_INGEST = SKILL_DIR / "references" / "workflow-ingest.md"

INGEST_HEADINGS = (
    "## Scenario: ingest",
)


def _ingest_section(text: str) -> str:
    """Return the slice that covers the ingest scenario heading.

    We look for the first known marker and return a generous window (4 KiB)
    so the check is robust to future copy-edit drift inside the scenario.
    """
    for marker in INGEST_HEADINGS:
        i = text.find(marker)
        if i >= 0:
            return text[i : i + 4000]
    return ""


def test_skill_md_no_fake_embed_fallback():
    """§3.2: SKILL.md must not advertise fake-embed as a production fallback.
    The fake embed_fn was a tests-only convenience; v0.3.0 freeze removes
    it from any agent-facing instruction text.
    """
    bad = re.compile(
        r"fake[\s_-]*embed|hash[\s_-]*based|"
        r"Only acceptable for tests|Only for tests",
        re.IGNORECASE,
    )
    text = SKILL_MD.read_text(encoding="utf-8")
    hits = bad.findall(text)
    assert not hits, (
        f"{SKILL_MD.name} contains fake-embed fallback language: {hits!r}. "
        f"Edit the prose to remove the production-fallback hint."
    )


def test_skill_md_ingest_directs_source_copy():
    """§3.6: SKILL.md ingest scenario + workflow-ingest.md must direct the
    host agent to copy the raw source file into <bundle>/sources/ before
    writing concept pages. Without this, every ingest silently breaks the
    OKF v0.1 immutable-source contract.
    """
    text = SKILL_MD.read_text(encoding="utf-8")
    section = _ingest_section(text)
    assert section, f"{SKILL_MD.name}: could not locate ingest scenario heading"
    assert "sources/" in section, (
        f"{SKILL_MD.name}: ingest scenario does not mention 'sources/'. "
        f"Add a 'copy raw source to <bundle>/sources/' step."
    )
    sl = section.lower()
    ok = (
        ("copy" in sl and "sources" in sl)
        or ("cp " in sl and "sources" in sl)
    )
    assert ok, (
        f"{SKILL_MD.name}: ingest scenario must include a copy-to-sources directive."
    )

    text = WORKFLOW_INGEST.read_text(encoding="utf-8")
    assert "sources/" in text, (
        "workflow-ingest.md does not mention 'sources/'."
    )
    ok = (
        ("copy" in text.lower() and "sources/" in text)
        or ("cp " in text.lower() and "sources/" in text)
    )
    assert ok, "workflow-ingest.md lacks a copy-to-sources directive."


def test_skill_md_log_entries_prepended():
    """§3.7: log.md must be prepended (newest-first per OKF §6). SKILL.md
    ingest scenario + workflow-ingest.md must direct the host agent to
    insert the new entry at the top, not append at the bottom.

    The check is line-scope: any line that mentions log.md must NOT use
    "append" against it; at least one log.md-mentioning line must use
    "prepend" / "insert at top".
    """
    text = SKILL_MD.read_text(encoding="utf-8")
    section = _ingest_section(text)
    assert section, f"{SKILL_MD.name}: could not locate ingest scenario heading"
    log_lines = [ln for ln in section.splitlines() if "log.md" in ln.lower()]
    assert log_lines, (
        f"{SKILL_MD.name}: ingest scenario does not mention 'log.md' at all"
    )
    bad = [ln for ln in log_lines if "append" in ln.lower()]
    assert not bad, (
        f"{SKILL_MD.name}: log.md step uses 'append' (must use 'prepend'): {bad!r}"
    )
    ok = [
        ln for ln in log_lines
        if "prepend" in ln.lower() or "insert at top" in ln.lower()
    ]
    assert ok, (
        f"{SKILL_MD.name}: no log.md line uses 'prepend' / 'insert at top'"
    )

    text = WORKFLOW_INGEST.read_text(encoding="utf-8")
    log_lines = [ln for ln in text.splitlines() if "log.md" in ln.lower()]
    bad = [ln for ln in log_lines if "append" in ln.lower()]
    assert not bad, (
        f"workflow-ingest.md log.md step uses 'append': {bad!r}"
    )
    ok = [
        ln for ln in log_lines
        if "prepend" in ln.lower() or "insert at top" in ln.lower()
    ]
    assert ok, "workflow-ingest.md log.md step lacks 'prepend' / 'insert at top'."
