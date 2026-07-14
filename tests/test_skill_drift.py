"""Release-gate for the Mneme 2.0 user and agent command surfaces.

Pre-Task A removes assertions that freeze the previous scenario taxonomy.
Later tasks complete the target sets below; this migration gate ensures that
intermediate commits can move toward them without reintroducing variant drift.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.release

ROOT = Path(__file__).resolve().parents[1]
SKILL_MD = ROOT / "skills" / "mneme" / "SKILL.md"
USER_INTENTS = {"dream", "search"}
AGENT_CLI = {"init", "lint", "reindex", "search", "dream", "convert"}


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


def test_user_surface_migrates_as_dream_search_pair():
    scenarios = _scenarios(SKILL_MD)
    assert "search" in scenarios
    if "dream" in scenarios:
        assert USER_INTENTS <= scenarios


def test_agent_cli_is_subset_of_2_0_contract_until_freeze_task():
    from mneme import cli

    parser = cli.build_parser()
    names = set(parser._subparsers._group_actions[0].choices)
    assert names <= AGENT_CLI
    assert "search" in names


def test_dream_is_read_only_when_advertised():
    text = SKILL_MD.read_text(encoding="utf-8").lower()
    if "dream" in _scenarios(SKILL_MD):
        assert any(
            phrase in text
            for phrase in (
                "dream is read-only",
                "dream returns a report",
                "no writes from dream",
            )
        )


def test_skill_cites_okf_version():
    pattern = re.compile(r"OKF\s+v?(\d+\.\d+)", re.IGNORECASE)
    hits = pattern.findall(SKILL_MD.read_text(encoding="utf-8"))
    assert hits, f"{SKILL_MD.name} does not cite an OKF version"
