"""Document consistency gates — Mneme 2.0 baseline.

Phase 0 freeze (v0.3.0) invariants are kept verbatim. Skill-first delivery
references are gated without contradicting the new dream/search surface that
later tasks will introduce.
"""
from pathlib import Path
import re
import pytest
pytestmark = pytest.mark.docs

ROOT = Path(__file__).resolve().parents[1]
CLAUDE_MD = ROOT / "CLAUDE.md"
AGENTS_MD = ROOT / "AGENTS.md"
SKILL_DIR = ROOT / "skills" / "mneme"
SKILL_MD = SKILL_DIR / "SKILL.md"
REFERENCES_DIR = SKILL_DIR / "references"

PROHIBITED = (
    "Strands",
    "@tool",
    "tools.py",
    "ingest.py",
    "query.py",
    "lint.py",
    "Click 风格",
)

PROHIBITED_AUTO_INSTALL = (
    "naive rag",
    "lazy install on first",
    "ensure_index_deps",
)

_NEGATED_AUTO_INSTALL = (
    "no auto-install",
    "no auto install",
    "no automatic install",
    "does not auto-install",
    "doesn't auto-install",
    "not auto-install",
)


# ---------------------------------------------------------------------------
# Phase 0 freeze (v0.3.0) — kept verbatim
# ---------------------------------------------------------------------------

def test_docs_no_deleted_layer_references():
    text = CLAUDE_MD.read_text(encoding="utf-8")
    for token in PROHIBITED:
        assert token not in text, (
            f"CLAUDE.md still mentions '{token}' (deleted in v2.1). "
            f"Edit the doc or move the reference into a 'History' footer."
        )


def test_agents_md_unaffected():
    """Sanity: AGENTS.md keeps its section structure."""
    text = AGENTS_MD.read_text(encoding="utf-8")
    assert "## " in text, "AGENTS.md lost its section structure"


# ---------------------------------------------------------------------------
# Mneme 2.0 §CLAUDE.md — OKF v0.1 + skill-first delivery
# ---------------------------------------------------------------------------

_USER_FACING_SECTIONS = (
    "这是什么",
    "目录结构",
    "下一步",
)


def _claude_md_user_facing_text() -> str:
    text = CLAUDE_MD.read_text(encoding="utf-8")
    out = []
    for section in _USER_FACING_SECTIONS:
        match = re.search(
            rf"^##\s+{re.escape(section)}\s*$",
            text,
            re.MULTILINE,
        )
        if not match:
            continue
        start = match.start()
        nxt = re.search(r"^##\s+", text[start + 1 :], re.MULTILINE)
        end = start + 1 + nxt.start() if nxt else len(text)
        out.append(text[start:end])
    return "\n".join(out)


def test_claude_md_no_wheel_install_in_workflow():
    text = _claude_md_user_facing_text()
    hits = re.findall(r"pip install mneme(?!\[\w)", text)
    assert not hits, (
        f"CLAUDE.md user-facing sections still teach `pip install mneme`: "
        f"{hits!r}. Mneme 2.0 ships via skill.sh, not PyPI."
    )


def test_claude_md_documents_skill_first_distribution():
    text = _claude_md_user_facing_text()
    assert "skill.sh" in text or "skills/mneme" in text, (
        "CLAUDE.md user-facing sections should mention the skill.sh "
        "distribution path / skills/mneme/ layout."
    )


def test_claude_md_documents_zero_dep_okf_core():
    text = CLAUDE_MD.read_text(encoding="utf-8")
    assert re.search(r"零依赖|zero.*dep|stdlib.*only|zero[- ]third", text, re.IGNORECASE), (
        "CLAUDE.md should explicitly document the OKF core's zero-dep "
        "baseline (zero hard deps; stdlib only)."
    )


def test_claude_md_references_okf_v0_1():
    text = CLAUDE_MD.read_text(encoding="utf-8")
    assert re.search(r"OKF\s*v?0\.1", text, re.IGNORECASE), (
        "CLAUDE.md must reference OKF v0.1 so the OKF contract is the "
        "single source of truth for bundle shape."
    )


def test_claude_md_user_facing_no_auto_install_claims():
    text = _claude_md_user_facing_text().lower()
    for phrase in PROHIBITED_AUTO_INSTALL:
        assert phrase not in text, f"CLAUDE.md user-facing sections claim {phrase!r}"
    assert "auto-install" not in text or any(
        phrase in text for phrase in _NEGATED_AUTO_INSTALL
    ), "CLAUDE.md user-facing sections suggest an auto-install flow"


# ---------------------------------------------------------------------------
# AGENTS.md / references/*.md path discipline
# ---------------------------------------------------------------------------

def test_agents_md_no_repo_relative_paths():
    text = AGENTS_MD.read_text(encoding="utf-8")
    patterns = (r"src/mneme/", r"python3 scripts/", r"\./scripts/")
    for pattern in patterns:
        hits = re.findall(pattern, text)
        assert not hits, (
            f"AGENTS.md still references repo-relative path {pattern!r}: {hits!r}"
        )


def test_references_no_repo_relative_paths():
    patterns = (r"src/mneme/", r"python3 scripts/mneme\.py", r"\./scripts/")
    for reference in REFERENCES_DIR.glob("*.md"):
        text = reference.read_text(encoding="utf-8")
        for pattern in patterns:
            hits = re.findall(pattern, text)
            assert not hits, (
                f"{reference.name} still contains repo-relative path {pattern!r}: {hits!r}"
            )


def test_references_no_auto_install_claims():
    for reference in REFERENCES_DIR.glob("*.md"):
        text = reference.read_text(encoding="utf-8").lower()
        for phrase in PROHIBITED_AUTO_INSTALL:
            assert phrase not in text, (
                f"{reference.name} still references {phrase!r}"
            )
        if "auto-install" in text:
            assert any(phrase in text for phrase in _NEGATED_AUTO_INSTALL), (
                f"{reference.name} suggests an auto-install flow"
            )
