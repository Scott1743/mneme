"""Phase 6 release-gate — SKILL language-variant drift detection.

The readiness assessment §P2 "Documentation has multiple sources of
truth" flagged that English and Chinese SKILL differ materially, and
that behavior changes depending on which client reads which variant.
``test_skill_text.py`` covers ingest-specific freeze rules; this
module covers the higher-level contract: the two variants must
advertise the SAME set of scenarios and the SAME OKF version, and
neither may resurrect the dream workflow that the v0.2.1rc1 freeze
removed.

If a future edit adds a scenario to one variant and forgets the
other, the host agent's behavior diverges per client locale. This
test makes the divergence fail at commit time.
"""
from __future__ import annotations

import re
from pathlib import Path
import pytest
pytestmark = pytest.mark.release

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "mneme"
SKILL_MD = SKILL_DIR / "SKILL.md"
SKILL_CN = SKILL_DIR / "SKILL cn.md"

# Scenarios the host agent advertises to its consumer. Both language
# variants MUST cover the same set — `init` / `reindex` / `search` /
# `ingest` / `query` / `lint`. `dream` is intentionally absent since
# the v0.2.1rc1 freeze removed it; re-introduction requires the
# Phase 5 safety TDD suite.
EXPECTED_SCENARIOS = {"init", "reindex", "search", "ingest", "query", "lint"}
FROZEN_SCENARIOS = {"dream"}


def _scenarios(path: Path) -> set:
    """Return the set of scenario names a SKILL variant declares.

    Matches both ``## Scenario: <name>`` (English) and
    ``## 场景：<name>`` (Chinese) headings.
    """
    text = path.read_text(encoding="utf-8")
    out = set()
    for m in re.finditer(
        r"^##\s+(?:Scenario|场景)[：:]\s*([a-z_]+)(?:\s|<|$)",
        text, re.MULTILINE | re.IGNORECASE,
    ):
        out.add(m.group(1).lower())
    return out


def test_skill_variants_advertise_same_scenarios():
    """EN and ZH SKILL must advertise the same scenario set. The
    assessment flagged that behavior changes depending on which
    client reads which variant; the fix is to make drift fail at
    commit time rather than at user-report time.
    """
    en = _scenarios(SKILL_MD)
    zh = _scenarios(SKILL_CN)
    assert en == zh, (
        f"SKILL.md and SKILL cn.md advertise different scenario sets:\n"
        f"  EN only: {sorted(en - zh)}\n"
        f"  ZH only: {sorted(zh - en)}\n"
        f"  shared:  {sorted(en & zh)}"
    )
    assert en == EXPECTED_SCENARIOS, (
        f"scenario set drifted from the expected contract:\n"
        f"  expected: {sorted(EXPECTED_SCENARIOS)}\n"
        f"  actual:   {sorted(en)}"
    )


def test_skill_variants_do_not_resurrect_dream():
    """v0.2.1rc1 freeze removed `dream` from both variants. Its
    recovery requires Phase 5 retrieval benchmark + find_orphans
    safety TDD + dry-run preview mode (per CHANGELOG 0.2.1 entry).
    A scenario heading resurrection here means someone bypassed the
    safety gate.
    """
    for path in (SKILL_MD, SKILL_CN):
        scenarios = _scenarios(path)
        assert not (scenarios & FROZEN_SCENARIOS), (
            f"{path.name} resurrected a frozen scenario: "
            f"{sorted(scenarios & FROZEN_SCENARIOS)}"
        )


def test_skill_variants_cite_same_okf_version():
    """Both variants must point at the same OKF spec version. The
    OKF version is the contract between wiki author and wiki reader;
    if the EN says 0.1 and the ZH says 0.2, a bilingual user sees
    two different formats.
    """
    pattern = re.compile(r"OKF\s+v?(\d+\.\d+)", re.IGNORECASE)
    versions = []
    for path in (SKILL_MD, SKILL_CN):
        text = path.read_text(encoding="utf-8")
        hits = pattern.findall(text)
        assert hits, f"{path.name} does not cite an OKF version"
        versions.append(hits[0])
    assert versions[0] == versions[1], (
        f"OKF version drift between SKILL variants: "
        f"EN={versions[0]!r}, ZH={versions[1]!r}"
    )
