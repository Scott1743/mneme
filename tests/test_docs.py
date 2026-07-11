"""Phase 0 freeze §3.5 — CLAUDE.md must not describe the v2.1-deleted Strands
agent layer or its deleted helper scripts.

The current CLAUDE.md still mentions Strands (deleted in 5e6c037/d06ab60 when
the L3 agent layer was dropped), lists `tools.py`/`ingest.py`/`query.py`/
`lint.py` (none of which exist after v2.1's thin-CLI refactor), and describes
the CLI as "Click 风格" when it's argparse. v0.3.0 freeze cleans this up.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLAUDE_MD = ROOT / "CLAUDE.md"
AGENTS_MD = ROOT / "AGENTS.md"

PROHIBITED = (
    "Strands",
    "@tool",
    "tools.py",
    "ingest.py",
    "query.py",
    "lint.py",
    "Click 风格",
)


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
