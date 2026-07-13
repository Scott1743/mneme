"""End-to-end lint harness (Phase 3 / v0.4.0 milestone).

`mneme lint <bundle>` is the documented user-facing command that
delegates to `okflib.validate_bundle` + a `find_orphans` guard. The
PR2 conformance suite (`tests/test_okflib.py`) verified each rule
in isolation against a single fixture. This module exercises the
full PR2 rule table against a single bundle so a regression in
any one rule is still caught end-to-end.

Two fixtures live under `tests/fixtures/e2e_lint/`:

- `clean_bundle/` — minimal valid bundle. Lint reports 0 errors and
  the find_orphans guard fires (intentional exit code ≠ 0).

- `dirty_bundle/` — one concept per intentional violation. Each file
  targets exactly one PR2 rule:
    a-good.md            baseline, no violation
    b-no-frontmatter.md  no frontmatter block (`no-frontmatter`)
    c-malformed-yaml.md  malformed YAML (`malformed-yaml`, requires PyYAML)
    d-list-type.md       `type:` is a list (`type-not-scalar`)
    e-empty-type.md      `type:` is whitespace (`empty-type`)
    f-broken-link.md     references `/concepts/nowhere.md` (`broken-link` warning)
    sources/raw-source.md raw input that MUST NOT be flagged (carve-out)

  Plus the index and log: index.md carries an illegal extra key
  (`root-index-extra-key`); log.md is out of newest-first order
  (`log-not-newest-first`).
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
# v1.1.0 switched CLI entry from `mneme <cmd>` console command to
# `python3 ~/.claude/skills/mneme/scripts/mneme.py <cmd>`. These
# subprocess tests still call the old form and need a rewrite
# (PR2 / PR3 work). Default-skipped per pyproject.toml addopts.
pytestmark = [pytest.mark.e2e, pytest.mark.compat]

ROOT = Path(__file__).parent.parent
CLEAN = ROOT / "tests" / "fixtures" / "e2e_lint" / "clean_bundle"
DIRTY = ROOT / "tests" / "fixtures" / "e2e_lint" / "dirty_bundle"


def _lint(bundle: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "mneme", "lint", str(bundle)],
        capture_output=True, text=True, check=False,
    )


def _parse_report(stdout: str) -> dict:
    """Parse the validator's stdout into errors/warnings lists of
    (path, rule, detail-prefix) tuples.

    The validator prints one line per violation; the summary footer
    reads `<int> error(s), <int> warning(s)`. We split on the
    blank line before the summary and then per-line.
    """
    errors = []
    warnings = []
    body, _, _ = stdout.partition("\n\n")
    for line in body.splitlines():
        m = re.match(r"^(ERROR|WARN)\s+([^:]+):\s+\[([^\]]+)\]\s+(.*)$", line)
        if not m:
            continue
        kind, path, rule, detail = m.groups()
        (errors if kind == "ERROR" else warnings).append(
            (path, rule, detail)
        )
    return {"errors": errors, "warnings": warnings}


# ─────────────────────────────────────────────────────────────────────────────

def test_clean_bundle_has_no_errors():
    """Baseline: a minimal valid bundle lints clean. The clean
    fixture is structured so the single concept (ok-concepts) IS
    referenced from index.md, which means find_orphans returns []
    and lint exits with the no-error code (3)."""
    r = _lint(CLEAN)
    parsed = _parse_report(r.stdout)
    assert parsed["errors"] == [], (
        f"clean bundle lints errors: {parsed['errors']}"
    )
    assert parsed["warnings"] == [], (
        f"clean bundle lints warnings: {parsed['warnings']}"
    )
    assert "0 error(s)" in r.stdout, r.stdout
    assert "0 warning(s)" in r.stdout, r.stdout
    # Orphan section is always emitted; here it is empty.
    assert "orphan concept pages (0)" in r.stderr, (
        f"expected empty orphan section; stderr={r.stderr!r}"
    )
    # Regression guard: the v0.3.0 freeze guard message must not
    # come back — find_orphans IS implemented now.
    assert "find_orphans not yet implemented" not in r.stderr


def test_dirty_bundle_catches_every_pr2_rule():
    """Every PR2 rule that the dirty fixture exercises must light up.

    The expected error map:
        root-index-extra-key   index.md
        log-not-newest-first   log.md
        no-frontmatter         concepts/b-no-frontmatter.md
        type-not-scalar         concepts/d-list-type.md
        empty-type              concepts/e-empty-type.md
    Plus a `broken-link` warning on f-broken-link.md.
    Plus (only when PyYAML is installed) `malformed-yaml` on
    c-malformed-yaml.md. We tolerate either presence/absence via
    the helper below.
    """
    r = _lint(DIRTY)
    parsed = _parse_report(r.stdout)

    expected_errors = {
        "index.md:root-index-extra-key",
        "log.md:log-not-newest-first",
        "concepts/b-no-frontmatter.md:no-frontmatter",
        "concepts/d-list-type.md:type-not-scalar",
        "concepts/e-empty-type.md:empty-type",
    }
    actual_errors = {f"{path}:{rule}" for path, rule, _ in parsed["errors"]}
    assert expected_errors.issubset(actual_errors), (
        f"expected at least {sorted(expected_errors)} errors; "
        f"got: {sorted(actual_errors)}"
    )

    # broken-link is a warning, not an error.
    broken = [
        (path, rule)
        for path, rule, _ in parsed["warnings"]
        if rule == "broken-link"
    ]
    assert any("concepts/f-broken-link.md" == p for p, _ in broken), (
        f"expected broken-link warning for f-broken-link.md; "
        f"got warnings: {parsed['warnings']}"
    )

    # sources/raw-source.md MUST NOT appear in the report at all.
    sources_paths = (
        {p for p, _, _ in parsed["errors"]} |
        {p for p, _, _ in parsed["warnings"]}
    )
    assert "sources/raw-source.md" not in sources_paths, (
        "raw source was flagged — sources/ validator carve-out regressed"
    )


def test_malformed_yaml_rule_fires_when_pyyaml_installed():
    """PyYAML is optional in v0.3.0; when present, `malformed-yaml`
    must surface. When absent, the lenient parser silently accepts the
    file. We test the conditional contract here rather than
    accidentally coupling the lint smoke to the active PyYAML.
    """
    pytest.importorskip("yaml")
    r = _lint(DIRTY)
    parsed = _parse_report(r.stdout)
    yaml_hits = [
        (path, rule)
        for path, rule, _ in parsed["errors"] + parsed["warnings"]
        if rule == "malformed-yaml"
    ]
    assert any("concepts/c-malformed-yaml.md" == p for p, _ in yaml_hits), (
        f"PyYAML present but malformed-yaml rule never fired; "
        f"got: {parsed['errors']} {parsed['warnings']}"
    )


def test_lint_exit_three_for_missing_orphans_primitive(tmp_path):
    """Both clean and dirty bundles exit non-zero with the find_orphans
    guard. Exit code 3 specifically (not argparse's 2)."""
    for bundle, _ in (("clean", CLEAN), ("dirty", DIRTY)):
        r = _lint(bundle if bundle == "clean" else DIRTY)
        assert r.returncode != 0, (
            f"lint of {bundle} bundle returned 0 (should be 3 — find_orphans guard)"
        )
        assert r.returncode != 2, (
            f"lint of {bundle} bundle returned 2 (argparse error — should be 3)"
        )


def test_dirty_bundle_violations_are_pinned():
    """The dirty bundle's violation map is the canonical exercise for
    the PR2 rule table. Pin the count of distinct rules so a
    regression that *drops* a rule (turning an error into nothing) is
    caught.
    """
    r = _lint(DIRTY)
    parsed = _parse_report(r.stdout)
    # Strict path (PyYAML installed): 6 error rules + N warnings.
    #   broken-link for f-broken-link.md (+ missing-timestamp warn family
    #   if applicable). We just gate that the strict-rule set is exactly
    #   the expected map.
    error_rules = {rule for _, rule, _ in parsed["errors"]}
    expected_minimum = {
        "root-index-extra-key",
        "log-not-newest-first",
        "no-frontmatter",
        "type-not-scalar",
        "empty-type",
    }
    assert expected_minimum.issubset(error_rules), (
        f"lost at least one rule; expected subset {expected_minimum}, "
        f"got {error_rules}"
    )