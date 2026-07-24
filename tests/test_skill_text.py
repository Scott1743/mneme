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
WORKFLOW_NIGHTLY = SKILL_DIR / "references" / "workflow-nightly-dream.md"
WORKFLOW_SEARCH = SKILL_DIR / "references" / "workflow-search.md"
TAG_GRAPH_CURATION = SKILL_DIR / "references" / "tag-graph-curation.md"
INDEX_DESIGN = SKILL_DIR / "references" / "index-design.md"


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
    assert "preserving the raw artifact" in text
    assert "creating its `Source` page" in text
    assert "only after approval and before writing" in text.lower()


def test_skill_offers_guarded_nightly_agent_task():
    skill = _text(SKILL_MD)
    nightly = _text(WORKFLOW_NIGHTLY)
    assert "daily 02:00 local-time task" in skill
    assert "Report only" in skill
    assert "Guarded auto-repair" in skill
    assert "host-agent recurring task" in skill
    assert "standing approval" in nightly
    assert "more than five concept pages" in nightly
    assert "Never change factual body text or raw sources" in nightly
    assert "git add" in nightly and "git commit" in nightly and "git push" in nightly


def test_approved_dream_preserves_source_and_prepends_log():
    text = _text(WORKFLOW_DREAM)
    assert "Copy the original source unchanged" in text
    assert "raw-sources/<artifact-name>" in text
    assert "sources/<slug>.md" in text
    assert "paper.md.raw" in text
    log_lines = [line for line in text.splitlines() if "log.md" in line]
    assert any("Prepend" in line for line in log_lines)
    assert all("append" not in line.lower() for line in log_lines)
    assert "YYYY-MM-DD dream |" in text


def test_dream_loads_tag_graph_curation_for_metadata_previews():
    skill = _text(SKILL_MD)
    curation = _text(TAG_GRAPH_CURATION)
    assert "load `references/tag-graph-curation.md`" in skill
    assert "1-3 tags" in curation and "at most 4" in curation
    assert "3-6 reusable entities" in curation
    assert "2-5 evidence-backed semantic relations" in curation
    assert "Never emit `mentions`" in curation
    assert "not OKF v0.1 validity rules" in curation


def test_search_reads_full_pages_and_never_writes():
    skill = _text(SKILL_MD)
    workflow = _text(WORKFLOW_SEARCH)
    assert "read each relevant Markdown page in full" in skill
    assert "Search never changes the bundle" in workflow
    assert "preview-and-approval" in workflow


def test_l2_is_explicit_and_does_not_change_authority():
    skill = _text(SKILL_MD)
    workflow = _text(WORKFLOW_SEARCH)
    assert "user explicitly requests semantic recall" in skill
    assert "never silently fall back" in workflow
    assert "bundle is authoritative" in workflow


def test_auto_search_is_query_routing_not_a_persisted_mode():
    skill = _text(SKILL_MD)
    workflow = _text(WORKFLOW_SEARCH)
    design = _text(INDEX_DESIGN)
    normalized_workflow = " ".join(workflow.split())
    normalized_design = " ".join(design.split())
    assert "Auto is not a persisted retrieval mode" in skill
    assert "must not run `reindex`" in skill
    assert "must not" in skill and "map itself to FTS5" in skill
    assert "Bare search and `--mode auto`" in normalized_workflow
    assert "`auto` is never stored there" in normalized_design
    assert "Choosing auto never runs `reindex`" in normalized_design


def test_skill_has_no_fake_embed_fallback():
    bad = re.compile(r"fake[\s_-]*embed|hash[\s_-]*based", re.IGNORECASE)
    assert not bad.findall(_text(SKILL_MD))


def test_legacy_workflow_files_are_removed():
    assert not (SKILL_DIR / "references" / "workflow-ingest.md").exists()
    assert not (SKILL_DIR / "references" / "workflow-query.md").exists()
