"""Release gate for the final dream/search and internal CLI surfaces."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.release

ROOT = Path(__file__).resolve().parents[1]
SKILL_MD = ROOT / "skills" / "mneme" / "SKILL.md"
USER_INTENTS = {"dream", "search"}
AGENT_CLI = {"init", "lint", "reindex", "search", "dream", "convert", "graph"}


def _scenarios(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8")
    return {
        match.group(1).lower()
        for match in re.finditer(
            r"^##\s+Scenario:\s*([a-z_]+)(?:\s|<|$)",
            text,
            re.MULTILINE | re.IGNORECASE,
        )
    }


def test_user_surface_is_exactly_dream_search_pair():
    assert _scenarios(SKILL_MD) == USER_INTENTS


def test_agent_cli_matches_contract_exactly():
    from mneme import cli

    parser = cli.build_parser()
    names = set(parser._subparsers._group_actions[0].choices)
    assert names == AGENT_CLI


def test_dream_is_read_only_when_advertised():
    text = SKILL_MD.read_text(encoding="utf-8").lower()
    assert "read-only audit step" in text
    assert "before every bundle write" in text


def test_skill_cites_okf_version():
    pattern = re.compile(r"OKF\s+v?(\d+\.\d+)", re.IGNORECASE)
    hits = pattern.findall(SKILL_MD.read_text(encoding="utf-8"))
    assert hits, f"{SKILL_MD.name} does not cite an OKF version"
