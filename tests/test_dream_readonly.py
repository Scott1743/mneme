"""v2.0 Task 6 — `mneme dream` read-only audit CLI contract.

The contract is four-fold:

  1. ``dream_audit(bundle)`` is pure-read — the bundle's bytes are not
     modified by the call.
  2. The ``dream`` CLI subparser has no ``--apply`` flag (writes are
     intentionally not exposed by the CLI; they live in SKILL.md).
  3. ``mneme dream`` never shells out via ``subprocess.run`` (no
     ``git``, no LLM-side effects). The test monkeypatches
     ``subprocess.run`` and asserts nothing was invoked that mentions
     ``git``.
  4. The audit report contains only raw distance candidates — no
     similarity thresholds like ``>=0.92``.

These tests also gate the broader v2.0 plan rule "dream is read-only,
SKILL.md orchestrates writes".
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
pytestmark = pytest.mark.unit


def _seed(tmp_path: Path) -> Path:
    b = tmp_path / "wiki"
    (b / "concepts").mkdir(parents=True, exist_ok=True)
    (b / "concepts" / "a.md").write_text(
        "---\ntype: Concept\ntitle: A\ndescription: alpha\n"
        "tags: [a]\ntimestamp: 2026-07-13T00:00:00Z\n---\nbody\n",
        encoding="utf-8",
    )
    (b / "index.md").write_text("# Index\n", encoding="utf-8")
    return b


def test_dream_audit_does_not_modify_bundle(tmp_path: Path) -> None:
    bundle = _seed(tmp_path)
    before = {p.relative_to(bundle): p.read_bytes() for p in bundle.rglob("*.md")}

    from mneme.dream import dream_audit
    dream_audit(bundle)

    after = {p.relative_to(bundle): p.read_bytes() for p in bundle.rglob("*.md")}
    assert before == after


def test_dream_cli_has_no_apply_flag() -> None:
    from mneme import cli
    parser = cli.build_parser()
    sub_actions = parser._subparsers._group_actions[0]
    dream_sp = sub_actions.choices["dream"]
    flags = {a.dest for a in dream_sp._actions if a.option_strings}
    assert "apply" not in flags, (
        "`mneme dream` exposes an --apply flag; the read-only contract "
        "is broken. Remove the flag — writes happen in SKILL.md."
    )


def test_dream_cli_does_not_shell_git(monkeypatch, tmp_path: Path) -> None:
    bundle = _seed(tmp_path)
    from mneme import cli
    called: list = []

    def spy(*args, **kw):
        called.append((args, kw))
        return subprocess.CompletedProcess(args[0] if args else "", 0, "", "")

    monkeypatch.setattr(subprocess, "run", spy)
    rc = cli.main(["dream", "--bundle", str(bundle)])
    assert rc == 0, "dream must succeed (read-only) on a clean bundle"
    joined = " ".join(str(a[0]) for a, _ in called)
    assert "git" not in joined, (
        f"`mneme dream` shelled out and the call mentioned 'git': "
        f"{called!r}"
    )


def test_dream_returns_only_raw_distance_no_similarity_threshold(tmp_path: Path) -> None:
    bundle = _seed(tmp_path)
    from mneme.dream import dream_audit
    report = dream_audit(bundle)
    text = str(report)
    assert "≥0.92" not in text and ">=0.92" not in text, (
        "dream report contains a similarity threshold; dream must "
        "report only raw distance candidates (no thresholds)."
    )
    assert "similarity" not in text.lower() or "raw distance" in text.lower(), (
        "dream report mentions 'similarity' without the "
        "'raw distance' qualifier — fix the wording."
    )


def test_dream_audit_handles_missing_bundle(tmp_path: Path) -> None:
    """dream_audit must not crash on a missing / non-directory bundle."""
    from mneme.dream import dream_audit
    missing = tmp_path / "no-such-bundle"
    report = dream_audit(missing)
    assert report["_meta"]["raw_distance_only"] is True
    assert "error" in report["_meta"]


def test_dream_and_lint_share_okf_hard_errors(tmp_path: Path) -> None:
    bundle = _seed(tmp_path)
    (bundle / "sources").mkdir()
    (bundle / "sources" / "raw.md").write_text("# Raw source\n", encoding="utf-8")

    from mneme import okflib
    from mneme.dream import dream_audit

    dream_errors = {
        (item["path"], item["rule"])
        for item in dream_audit(bundle)["okf_hard_rules"]
    }
    lint_errors = {
        (item["path"], item["code"])
        for item in okflib.lint_bundle(bundle)["diagnostics"]
        if item["severity"] == "ERROR" and item["code"] != "MNEME-TAG-MISSING"
    }
    assert dream_errors == lint_errors == {("sources/raw.md", "no-frontmatter")}


def test_dream_cli_resolves_bundle_via_config_without_bundle_flag(tmp_path: Path) -> None:
    """`mneme dream` without --bundle must resolve via config.toml, not crash.

    Regression guard for the TypeError caused by passing ``Path(args.config)``
    (where ``args.config`` is None by default) to ``_resolve_bundle``. The
    fix routes through ``_resolve_bundle(args)`` like the other subcommands.
    """
    bundle = _seed(tmp_path)
    cfg = tmp_path / "config.toml"
    cfg.write_text(f'bundle_path = "{bundle}"\n', encoding="utf-8")

    from mneme import cli

    rc = cli.main(["dream", "--config", str(cfg)])
    assert rc == 0, "dream without --bundle must resolve via config and succeed"
