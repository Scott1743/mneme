"""Phase 6 release-gate — SKILL scenario + OKF-version drift detection.

The readiness assessment §P2 "Documentation has multiple sources of
truth" flagged that English and Chinese SKILL differ materially. v1.1.0
collapsed to a single English SKILL; this module now guards the
scenario-set contract on the single source of truth instead of cross-
variant drift.

If a future edit adds/removes a scenario without updating the test's
expected set, the host agent's behavior diverges from the contract.
This test makes the divergence fail at commit time.
"""
from __future__ import annotations

import re
from pathlib import Path
import pytest
pytestmark = pytest.mark.release

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "mneme"
SKILL_MD = SKILL_DIR / "SKILL.md"

# Scenarios the host agent advertises to its consumer. The single SKILL
# variant MUST cover this set — `init` / `reindex` / `search` /
# `ingest` / `query` / `lint`. `dream` is intentionally absent since
# the v0.2.1rc1 freeze removed it; re-introduction requires the
# Phase 5 safety TDD suite.
EXPECTED_SCENARIOS = {"init", "reindex", "search", "ingest", "query", "lint"}
FROZEN_SCENARIOS = {"dream"}


def _scenarios(path: Path) -> set:
    """Return the set of scenario names SKILL.md declares."""
    text = path.read_text(encoding="utf-8")
    out = set()
    for m in re.finditer(
        r"^##\s+Scenario:\s*([a-z_]+)(?:\s|<|$)",
        text, re.MULTILINE | re.IGNORECASE,
    ):
        out.add(m.group(1).lower())
    return out


def test_skill_advertises_expected_scenarios():
    """SKILL.md must advertise the documented scenario set."""
    actual = _scenarios(SKILL_MD)
    assert actual == EXPECTED_SCENARIOS, (
        f"SKILL.md scenario set drifted from the contract:\n"
        f"  expected: {sorted(EXPECTED_SCENARIOS)}\n"
        f"  actual:   {sorted(actual)}\n"
        f"  missing:  {sorted(EXPECTED_SCENARIOS - actual)}\n"
        f"  extra:    {sorted(actual - EXPECTED_SCENARIOS)}"
    )


def test_skill_does_not_resurrect_dream():
    """v0.2.1rc1 freeze removed `dream`. Its recovery requires Phase 5
    retrieval benchmark + find_orphans safety TDD + dry-run preview
    mode (per CHANGELOG 0.2.1 entry). A scenario heading resurrection
    here means someone bypassed the safety gate.
    """
    scenarios = _scenarios(SKILL_MD)
    assert not (scenarios & FROZEN_SCENARIOS), (
        f"{SKILL_MD.name} resurrected a frozen scenario: "
        f"{sorted(scenarios & FROZEN_SCENARIOS)}"
    )


def test_skill_cites_okf_version():
    """SKILL.md must point at a specific OKF spec version. The OKF
    version is the contract between wiki author and wiki reader."""
    pattern = re.compile(r"OKF\s+v?(\d+\.\d+)", re.IGNORECASE)
    text = SKILL_MD.read_text(encoding="utf-8")
    hits = pattern.findall(text)
    assert hits, f"{SKILL_MD.name} does not cite an OKF version"
