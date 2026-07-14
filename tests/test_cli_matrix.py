"""Mneme 2.0.1 CLI matrix and bundle-resolution contract."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from mneme import cli, indexlib, tools_helpers

pytestmark = pytest.mark.unit


EXPECTED_COMMANDS = {"init", "lint", "reindex", "search", "dream", "convert"}


def _subcommands(parser: argparse.ArgumentParser) -> dict[str, argparse.ArgumentParser]:
    return parser._subparsers._group_actions[0].choices


def test_build_parser_exposes_only_supported_subcommands():
    parser = cli.build_parser()
    assert isinstance(parser, argparse.ArgumentParser)
    assert set(_subcommands(parser)) == EXPECTED_COMMANDS


def test_dream_parser_has_no_apply_flag():
    dream = _subcommands(cli.build_parser())["dream"]
    option_strings = {flag for action in dream._actions for flag in action.option_strings}
    assert "--apply" not in option_strings


def test_resolve_bundle_environment_has_highest_priority(tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "config.toml").write_text(
        f'bundle_path = "{tmp_path / "configured"}"\n', encoding="utf-8"
    )
    env = {"MNEME_BUNDLE": str(tmp_path / "environment")}

    assert tools_helpers.resolve_bundle(
        config_dir=config_dir, env=env, cwd=tmp_path
    ) == tmp_path / "environment"


def test_resolve_bundle_uses_explicit_config_dir(tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    configured = tmp_path / "configured"
    (config_dir / "config.toml").write_text(
        f'bundle_path = "{configured}"\n', encoding="utf-8"
    )

    assert tools_helpers.resolve_bundle(
        config_dir=config_dir, env={}, cwd=tmp_path
    ) == configured


def test_resolve_bundle_honors_mneme_config_dir(tmp_path):
    config_dir = tmp_path / "custom-config"
    config_dir.mkdir()
    configured = tmp_path / "configured"
    (config_dir / "config.toml").write_text(
        f'bundle_path = "{configured}"\n', encoding="utf-8"
    )

    assert tools_helpers.resolve_bundle(
        env={"MNEME_CONFIG_DIR": str(config_dir)}, cwd=tmp_path
    ) == configured


def test_resolve_bundle_defaults_to_home_config(tmp_path):
    home = tmp_path / "home"
    config_dir = home / ".config" / "mneme"
    config_dir.mkdir(parents=True)
    configured = tmp_path / "configured"
    (config_dir / "config.toml").write_text(
        f'bundle_path = "{configured}"\n', encoding="utf-8"
    )

    assert tools_helpers.resolve_bundle(
        env={"HOME": str(home)}, cwd=tmp_path
    ) == configured


def test_resolve_bundle_walks_up_from_cwd_for_index(tmp_path):
    bundle = tmp_path / "bundle"
    nested = bundle / "notes" / "deep"
    nested.mkdir(parents=True)
    (bundle / "index.md").write_text("# Index\n", encoding="utf-8")

    assert tools_helpers.resolve_bundle(
        config_dir=tmp_path / "missing-config", env={}, cwd=nested
    ) == bundle


def test_resolve_bundle_falls_back_to_wiki_directory(tmp_path):
    wiki = tmp_path / "wiki"
    wiki.mkdir()

    assert tools_helpers.resolve_bundle(
        config_dir=tmp_path / "missing-config", env={}, cwd=tmp_path
    ) == wiki


def test_resolve_bundle_returns_none_when_chain_is_empty(tmp_path):
    assert tools_helpers.resolve_bundle(
        config_dir=tmp_path / "missing-config", env={}, cwd=tmp_path
    ) is None


def test_init_exit_codes_are_zero_then_one(tmp_path):
    bundle = tmp_path / "wiki"
    config_path = tmp_path / "config" / "config.toml"

    assert cli.main(["init", str(bundle), "--config", str(config_path)]) == 0
    assert cli.main(["init", str(bundle), "--config", str(config_path)]) == 1


def test_lint_exit_code_is_zero_without_errors(tmp_path):
    bundle = tmp_path / "wiki"
    bundle.mkdir()
    (bundle / "index.md").write_text("# Index\n", encoding="utf-8")

    assert cli.main(["lint", "--bundle", str(bundle)]) == 0


def test_lint_exit_code_is_one_with_errors(tmp_path):
    bundle = tmp_path / "wiki"
    bundle.mkdir()
    (bundle / "broken.md").write_text("no frontmatter\n", encoding="utf-8")

    assert cli.main(["lint", "--bundle", str(bundle)]) == 1


def test_reindex_exit_code_is_one_when_bundle_is_missing(tmp_path):
    assert cli.main(
        ["reindex", "--bundle", str(tmp_path / "missing")]
    ) == 1


def test_search_exit_code_is_zero_for_empty_candidates(tmp_path, monkeypatch, capsys):
    bundle = tmp_path / "wiki"
    bundle.mkdir()
    monkeypatch.setattr(
        indexlib,
        "search",
        lambda query, db, k: {"query": query, "candidates": []},
    )
    # Drop a sentinel index.db so cmd_search takes the FTS5 path
    # rather than the L0 grep fallback.
    (bundle / ".mneme").mkdir()
    (bundle / ".mneme" / "index.db").write_bytes(b"")

    assert cli.main(["search", "absent", "--bundle", str(bundle), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == {"query": "absent", "candidates": []}


def test_search_exit_code_is_one_when_bundle_is_missing(tmp_path):
    assert cli.main(
        ["search", "anything", "--bundle", str(tmp_path / "missing")]
    ) == 1


def test_dream_exit_code_is_always_zero(tmp_path):
    assert cli.main(["dream", "--bundle", str(tmp_path / "missing")]) == 0
