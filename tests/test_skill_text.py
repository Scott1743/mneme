"""Text-level release gates for the dream/search host-agent contract."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.docs

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "mneme"
SKILL_MD = SKILL_DIR / "SKILL.md"
WORKFLOW_DREAM = SKILL_DIR / "references" / "workflow-dream.md"
WORKFLOW_SEARCH = SKILL_DIR / "references" / "workflow-search.md"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_skill_has_exactly_dream_and_search_scenarios():
    scenarios = set(
        re.findall(r"^## Scenario: ([a-z_]+)", _text(SKILL_MD), re.MULTILINE)
    )
    assert scenarios == {"dream", "search"}


def test_dream_requires_approval_before_bundle_writes():
    text = _text(SKILL_MD)
    approval = text.index("Require explicit user approval")
    workflow_load = text.index("load `references/workflow-dream.md`")
    assert approval < workflow_load
    assert "including copying the raw source into `sources/`" in text
    assert "only after approval and before writing" in text.lower()


def test_approved_dream_preserves_source_and_prepends_log():
    text = _text(WORKFLOW_DREAM)
    assert "Copy the original source unchanged" in text
    assert "sources/<basename>" in text
    log_lines = [line for line in text.splitlines() if "log.md" in line]
    assert any("Prepend" in line for line in log_lines)
    assert all("append" not in line.lower() for line in log_lines)
    assert "YYYY-MM-DD dream |" in text


def test_search_reads_full_pages_and_never_writes():
    skill = _text(SKILL_MD)
    workflow = _text(WORKFLOW_SEARCH)
    assert "read each relevant Markdown page in full" in skill
    assert "Search never changes the bundle" in workflow
    assert "preview-and-approval" in workflow


def test_skill_has_no_fake_embed_fallback():
    bad = re.compile(r"fake[\s_-]*embed|hash[\s_-]*based", re.IGNORECASE)
    assert not bad.findall(_text(SKILL_MD))


def test_legacy_workflow_files_are_removed():
    assert not (SKILL_DIR / "references" / "workflow-ingest.md").exists()
    assert not (SKILL_DIR / "references" / "workflow-query.md").exists()
