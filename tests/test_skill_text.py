"""Phase 0 freeze §3.2 / §3.6 / §3.7 — text-level guards on SKILL*.md and
workflow-ingest.md. Each test asserts a missing doc directive that must be
fixed before PR1 lands.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "mneme"
SKILL_MD = SKILL_DIR / "SKILL.md"
SKILL_CN = SKILL_DIR / "SKILL cn.md"
WORKFLOW_INGEST = SKILL_DIR / "references" / "workflow-ingest.md"

INGEST_HEADINGS = (
    "## Scenario: ingest",
    "## 场景：摄入",
    "## 摄入",
)


def _ingest_section(text: str) -> str:
    """Return the slice that covers the ingest scenario heading.

    Different language variants use slightly different `##` headings; we look
    for the first known marker and return a generous window (4 KiB) so the
    check is robust to future copy-edit drift inside the scenario.
    """
    for marker in INGEST_HEADINGS:
        i = text.find(marker)
        if i >= 0:
            return text[i : i + 4000]
    return ""


def test_skill_md_no_fake_embed_fallback():
    """§3.2: SKILL.md and SKILL cn.md must not advertise fake-embed as a
    production fallback. The fake embed_fn was a tests-only convenience; v0.3.0
    freeze removes it from any agent-facing instruction text.
    """
    bad = re.compile(
        r"fake[\s_-]*embed|hash[\s_-]*based|"
        r"Only acceptable for tests|Only for tests|测试 fake embedding",
        re.IGNORECASE,
    )
    for path in (SKILL_MD, SKILL_CN):
        text = path.read_text(encoding="utf-8")
        hits = bad.findall(text)
        assert not hits, (
            f"{path.name} contains fake-embed fallback language: {hits!r}. "
            f"Edit the prose to remove the production-fallback hint."
        )


def test_skill_md_ingest_directs_source_copy():
    """§3.6: SKILL*.md ingest scenario + workflow-ingest.md must direct the
    host agent to copy the raw source file into <bundle>/sources/ before
    writing concept pages. Without this, every ingest silently breaks the
    OKF v0.1 immutable-source contract.
    """
    for path in (SKILL_MD, SKILL_CN):
        text = path.read_text(encoding="utf-8")
        section = _ingest_section(text)
        assert section, f"{path.name}: could not locate ingest scenario heading"
        assert "sources/" in section, (
            f"{path.name}: ingest scenario does not mention 'sources/'. "
            f"Add a 'copy raw source to <bundle>/sources/' step."
        )
        sl = section.lower()
        ok = (
            ("copy" in sl and "sources" in sl)
            or "复制" in section
            or ("cp " in sl and "sources" in sl)
        )
        assert ok, (
            f"{path.name}: ingest scenario must include a copy-to-sources "
            f"directive (English or Chinese)."
        )

    text = WORKFLOW_INGEST.read_text(encoding="utf-8")
    assert "sources/" in text, (
        "workflow-ingest.md does not mention 'sources/'."
    )
    ok = (
        ("copy" in text.lower() and "sources/" in text)
        or "复制" in text
        or ("cp " in text.lower() and "sources/" in text)
    )
    assert ok, "workflow-ingest.md lacks a copy-to-sources directive."


def test_skill_md_log_entries_prepended():
    """§3.7: log.md must be prepended (newest-first per OKF §6). SKILL*.md
    ingest scenario + workflow-ingest.md must direct the host agent to insert
    the new entry at the top, not append at the bottom.
    """
    for path in (SKILL_MD, SKILL_CN):
        text = path.read_text(encoding="utf-8")
        section = _ingest_section(text)
        assert section, f"{path.name}: could not locate ingest scenario heading"
        sl = section.lower()
        bad = ("append" in sl and "log.md" in sl) or (
            "append" in section and "log.md" in section
        )
        assert not bad, (
            f"{path.name}: ingest scenario says to append, not prepend. "
            f"Replace 'append' with 'prepend' (or '顶部插入') in the log step."
        )
        ok = "prepend" in sl or "顶部" in section or "insert at top" in sl
        assert ok, (
            f"{path.name}: ingest scenario lacks a 'prepend' / '顶部' "
            f"directive for the log.md edit step."
        )

    text = WORKFLOW_INGEST.read_text(encoding="utf-8").lower()
    bad = "append" in text and "log.md" in text
    assert not bad, (
        "workflow-ingest.md step says to append log.md. Replace with prepend."
    )
    ok = "prepend" in text or "顶部" in WORKFLOW_INGEST.read_text(encoding="utf-8")
    assert ok, "workflow-ingest.md lacks a prepend directive for log.md."
