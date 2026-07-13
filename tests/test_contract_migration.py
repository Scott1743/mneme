from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SKILL = (ROOT / "skills/mneme/SKILL.md").read_text(encoding="utf-8")
RELEASE = (ROOT / "tests/test_release_layout.py").read_text(encoding="utf-8")
DRIFT = (ROOT / "tests/test_skill_drift.py").read_text(encoding="utf-8")
DOCS = (ROOT / "tests/test_docs.py").read_text(encoding="utf-8")
ZERO_DEP = (ROOT / "tests/test_zero_dep.py").read_text(encoding="utf-8")


def _user_documents() -> str:
    """Concatenate the user-visible documents this test guards."""
    parts: list[str] = []
    for path in (ROOT / "CLAUDE.md", ROOT / "AGENTS.md",
                 ROOT / "skills/mneme/SKILL.md"):
        if path.exists():
            parts.append(path.read_text(encoding="utf-8"))
    references_dir = ROOT / "skills" / "mneme" / "references"
    if references_dir.is_dir():
        for reference in sorted(references_dir.glob("*.md")):
            parts.append(reference.read_text(encoding="utf-8"))
    return "\n".join(parts).lower()


def test_skill_no_bilingual_skill_cn():
    assert "SKILL.cn.md" not in SKILL, "drop reference; 1.1.0 removed the variant"


def test_skill_state_dream_is_read_only_when_advertised():
    lower = SKILL.lower()
    if "scenario: dream" in lower:
        assert any(
            line in lower
            for line in ("dream is read-only", "dream returns a report", "no writes from dream")
        )


def test_release_layout_no_wheel_no_project_block():
    pj = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "[project]" not in pj
    assert "wheel" not in RELEASE.lower(), "tests still reference a wheel"


def test_skill_drift_no_lazy_install_claim():
    assert "ensure_index_deps" not in DRIFT
    assert "lazy install" not in DRIFT.lower() or "first search/reindex" not in DRIFT.lower()


def test_docs_no_naive_rag_in_user_docs():
    forbidden = ["naive rag", "lazy install on first"]
    user_docs = _user_documents()
    for phrase in forbidden:
        assert phrase not in user_docs, f"user docs still reference {phrase!r}"
    # ``auto-install`` is allowed only when the surrounding text explicitly
    # says the skill does NOT auto-install. The same negated-context rule
    # lives in tests/test_docs.py and is mirrored here so the migration gate
    # surfaces the same problem.
    if "auto-install" in user_docs:
        negated = (
            "no auto-install",
            "no auto install",
            "does not auto-install",
            "doesn't auto-install",
            "is no auto-install",
        )
        assert any(phrase in user_docs for phrase in negated), (
            "user docs reference 'auto-install' without a negation"
        )


def test_zero_dep_no_lazy_install_contract():
    assert "ensure_index_deps" not in ZERO_DEP
    assert "lazy-install" not in ZERO_DEP.lower()
    assert "falls_back_to_lazy_install" not in ZERO_DEP.lower()


def test_python_311_min():
    assert sys.version_info >= (3, 11)
