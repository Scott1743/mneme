"""Document consistency gates — Phase 0 freeze (v0.3.0) + v1.1.0 skill-first.

The first two tests pin Phase 0 / v0.3.0 freeze invariants (no Strands,
no @tool, no deleted helper scripts, no Click 风格). The remaining
tests pin the v1.1.0 delivery contract (skill-first, zero-dep OKF
core, L2 lazy install) across CLAUDE.md, AGENTS.md, SKILL.md, and
the references/ docs.
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
    """Sanity: AGENTS.md is the v2.1-current doc and must keep its 7-scenario
    structure. This guards against accidentally editing the wrong file in the
    freeze PR.
    """
    text = AGENTS_MD.read_text(encoding="utf-8")
    assert "dream" in text.lower(), "AGENTS.md lost the dream section reference"
    assert "## " in text, "AGENTS.md lost its section structure"


# ---------------------------------------------------------------------------
# v1.1.0 §6.1 — CLAUDE.md delivery contract
# ---------------------------------------------------------------------------

# Sections of CLAUDE.md that face end users / new contributors. Wheel-install
# language is forbidden here; pip-install-mneme (whole-package) is forbidden;
# skill.sh + zero-dep are required.
_USER_FACING_SECTIONS = (
    "这是什么",
    "目录结构",
    "下一步",
)


def _claude_md_user_facing_text() -> str:
    """Concatenate just the user-facing sections of CLAUDE.md.

    We extract the named top-level sections so wheel-install guidance in
    a 'History' footer (if any) doesn't false-positive the contract.
    """
    text = CLAUDE_MD.read_text(encoding="utf-8")
    out = []
    for section in _USER_FACING_SECTIONS:
        m = re.search(
            rf"^##\s+{re.escape(section)}\s*$",
            text, re.MULTILINE,
        )
        if not m:
            continue
        start = m.start()
        # Find next ## header.
        nxt = re.search(r"^##\s+", text[start + 1 :], re.MULTILINE)
        end = start + 1 + nxt.start() if nxt else len(text)
        out.append(text[start:end])
    return "\n".join(out)


def test_claude_md_no_wheel_install_in_workflow():
    """User-facing sections of CLAUDE.md must not teach `pip install mneme`."""
    text = _claude_md_user_facing_text()
    hits = re.findall(r"pip install mneme(?!\[\w)", text)
    assert not hits, (
        f"CLAUDE.md user-facing sections still teach `pip install mneme`: "
        f"{hits!r}. v1.1.0 ships via skill.sh, not PyPI."
    )


def test_claude_md_documents_skill_first_distribution():
    """CLAUDE.md user-facing sections must mention skill.sh + skill-first."""
    text = _claude_md_user_facing_text()
    assert "skill.sh" in text or "skills/mneme" in text, (
        "CLAUDE.md user-facing sections should mention the skill.sh "
        "distribution path / skills/mneme/ layout."
    )


def test_claude_md_documents_zero_dep_okf_core():
    """CLAUDE.md should explicitly call out OKF core's zero-dep baseline."""
    text = CLAUDE_MD.read_text(encoding="utf-8")
    assert re.search(r"零依赖|zero.*dep|stdlib.*only|zero[- ]third", text, re.IGNORECASE), (
        "CLAUDE.md should explicitly document the OKF core's zero-dep "
        "baseline (zero hard deps; stdlib only)."
    )


# ---------------------------------------------------------------------------
# v1.1.0 §6.2 — AGENTS.md path discipline
# ---------------------------------------------------------------------------

def test_agents_md_no_repo_relative_paths():
    """AGENTS.md must not reference the old src/ layout or repo-relative scripts."""
    text = AGENTS_MD.read_text(encoding="utf-8")
    patterns = (r"src/mneme/", r"python3 scripts/", r"\./scripts/")
    for pat in patterns:
        hits = re.findall(pat, text)
        assert not hits, (
            f"AGENTS.md still references repo-relative path {pat!r}: {hits!r}"
        )


# ---------------------------------------------------------------------------
# v1.1.0 §6.4 — references/*.md L2 lazy install + path discipline
# ---------------------------------------------------------------------------

def test_references_documents_l2_lazy_install():
    """workflow-query.md (and the wider references/) should mention
    L2 lazy install so users aren't surprised by the first-call download."""
    workflow_query = (REFERENCES_DIR / "workflow-query.md").read_text(encoding="utf-8")
    assert re.search(r"(ensure_index_deps|lazy|first.*install|first.*use.*install)", workflow_query, re.IGNORECASE), (
        "references/workflow-query.md should document the L2 lazy-install "
        "behaviour so users aren't surprised by the first-call model download."
    )


def test_references_no_repo_relative_paths():
    """All 6 references/*.md files must be free of repo-relative paths."""
    patterns = (r"src/mneme/", r"python3 scripts/mneme\.py", r"\./scripts/")
    for ref in REFERENCES_DIR.glob("*.md"):
        text = ref.read_text(encoding="utf-8")
        for pat in patterns:
            hits = re.findall(pat, text)
            assert not hits, (
                f"{ref.name} still contains repo-relative path {pat!r}: {hits!r}"
            )
