"""Persistent optional L2 retrieval contract for Mneme 3.3.

These tests use injected embedders and do not require the optional packages,
so the mode-selection contract remains covered by the default offline suite.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from mneme import cli, indexlib
from mneme.config import read_config, retrieval_mode, write_config

pytestmark = pytest.mark.unit


def _bundle(tmp_path: Path) -> tuple[Path, Path]:
    bundle = tmp_path / "wiki"
    bundle.mkdir()
    config = tmp_path / "config.toml"
    write_config(config, {"bundle_path": str(bundle)})
    return bundle, config


def test_reindex_help_exposes_persistent_mode_controls():
    parser = cli.build_parser()
    reindex = parser._subparsers._group_actions[0].choices["reindex"]
    flags = {flag for action in reindex._actions for flag in action.option_strings}
    assert {"--l2", "--fts5"} <= flags


def test_l2_activation_is_persisted_only_after_success(tmp_path, monkeypatch):
    bundle, config = _bundle(tmp_path)

    def fail_embedder():
        raise indexlib.FastEmbedUnavailableError("install fastembed")

    monkeypatch.setattr(indexlib, "default_embed_fn", fail_embedder)
    assert cli.main(["reindex", "--l2", "--config", str(config)]) == 1
    assert retrieval_mode(config) == "fts5"

    embedder = indexlib.Embedder(lambda texts: [[0.0] for _ in texts], "test")
    result = indexlib.ReindexResult(1, 1, 0, indexlib.l2_index_path(bundle))
    monkeypatch.setattr(indexlib, "default_embed_fn", lambda: embedder)
    monkeypatch.setattr(indexlib, "reindex_bundle", lambda root, embed: result)

    assert cli.main(["reindex", "--l2", "--config", str(config)]) == 0
    assert read_config(config)["active_retrieval_mode"] == "l2"


def test_active_l2_search_does_not_require_a_flag(tmp_path, monkeypatch, capsys):
    bundle, config = _bundle(tmp_path)
    write_config(config, {"bundle_path": str(bundle), "active_retrieval_mode": "l2"})
    indexlib.l2_index_path(bundle).parent.mkdir()
    indexlib.l2_index_path(bundle).touch()
    embedder = indexlib.Embedder(lambda texts: [[0.0] for _ in texts], "test")
    monkeypatch.setattr(indexlib, "default_embed_fn", lambda: embedder)
    monkeypatch.setattr(
        indexlib,
        "search_bundle",
        lambda root, query, k, embed_fn: [
            {
                "path": "concepts/a.md",
                "title": "A",
                "text": "semantic hit",
                "distance": 0.42,
            }
        ],
    )

    assert cli.main(["search", "question", "--config", str(config), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["candidates"] == [
        {
            "path": "concepts/a.md",
            "title": "A",
            "snippet": "semantic hit",
            "distance": 0.42,
        }
    ]


def test_legacy_search_l2_flag_cannot_switch_an_fts5_bundle(tmp_path, capsys):
    _, config = _bundle(tmp_path)

    assert cli.main(["search", "question", "--l2", "--config", str(config)]) == 1
    assert "no longer switches modes" in capsys.readouterr().err


def test_active_l2_missing_index_does_not_fallback_to_fts5(tmp_path, monkeypatch, capsys):
    _, config = _bundle(tmp_path)
    write_config(config, {"bundle_path": str(tmp_path / "wiki"), "active_retrieval_mode": "l2"})
    monkeypatch.setattr(cli, "_cmd_search_grep", lambda *args: pytest.fail("must not grep"))

    assert cli.main(["search", "question", "--config", str(config)]) == 1
    assert "no L2 index" in capsys.readouterr().err


def test_active_l2_reindex_without_flag_uses_l2(tmp_path, monkeypatch):
    bundle, config = _bundle(tmp_path)
    write_config(config, {"bundle_path": str(bundle), "active_retrieval_mode": "l2"})
    embedder = indexlib.Embedder(lambda texts: [[0.0] for _ in texts], "test")
    result = indexlib.ReindexResult(1, 1, 0, indexlib.l2_index_path(bundle))
    monkeypatch.setattr(indexlib, "default_embed_fn", lambda: embedder)
    monkeypatch.setattr(indexlib, "reindex_bundle", lambda root, embed: result)

    assert cli.main(["reindex", "--config", str(config)]) == 0
    assert retrieval_mode(config) == "l2"


def test_fts5_switch_is_explicit_and_preserves_l2_cache(tmp_path, monkeypatch):
    bundle, config = _bundle(tmp_path)
    write_config(config, {"bundle_path": str(bundle), "active_retrieval_mode": "l2"})
    l2_db = indexlib.l2_index_path(bundle)
    l2_db.parent.mkdir()
    l2_db.write_bytes(b"semantic cache")
    monkeypatch.setattr(indexlib, "reindex_paths", lambda paths, root: 0)

    assert cli.main(["reindex", "--fts5", "--config", str(config)]) == 0
    assert retrieval_mode(config) == "fts5"
    assert l2_db.read_bytes() == b"semantic cache"


def test_upgrade_then_downgrade_routes_bare_search_to_the_active_mode(
    tmp_path, monkeypatch, capsys
):
    """One shared ``search`` command follows L1 -> L2 -> L1 transitions."""
    bundle, config = _bundle(tmp_path)
    l2_db = indexlib.l2_index_path(bundle)
    l2_db.parent.mkdir()
    l2_db.write_bytes(b"semantic cache")
    fts_db = indexlib.fts_index_path(bundle)
    fts_db.write_bytes(b"fts cache")
    embedder = indexlib.Embedder(lambda texts: [[0.0] for _ in texts], "test")
    result = indexlib.ReindexResult(1, 1, 0, l2_db)
    monkeypatch.setattr(indexlib, "default_embed_fn", lambda: embedder)
    monkeypatch.setattr(indexlib, "reindex_bundle", lambda root, embed: result)
    monkeypatch.setattr(indexlib, "reindex_paths", lambda paths, root: 1)

    calls: list[str] = []

    def semantic_search(root, query, k, embed_fn):
        calls.append("l2")
        return [{"path": "concepts/l2.md", "title": "L2", "text": "semantic"}]

    def fts_search(query, db, k):
        calls.append("fts5")
        return {
            "query": query,
            "candidates": [{"path": "concepts/l1.md", "title": "L1", "snippet": "lexical"}],
        }

    monkeypatch.setattr(indexlib, "search_bundle", semantic_search)
    monkeypatch.setattr(indexlib, "search", fts_search)

    assert cli.main(["reindex", "--l2", "--config", str(config)]) == 0
    capsys.readouterr()
    assert cli.main(["search", "question", "--config", str(config), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["candidates"][0]["path"] == "concepts/l2.md"

    assert cli.main(["reindex", "--fts5", "--config", str(config)]) == 0
    capsys.readouterr()
    assert cli.main(["search", "question", "--config", str(config), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["candidates"][0]["path"] == "concepts/l1.md"
    assert calls == ["l2", "fts5"]
    assert l2_db.read_bytes() == b"semantic cache"


def test_fts5_and_l2_cache_paths_are_independent(tmp_path):
    bundle = tmp_path / "wiki"
    assert indexlib.fts_index_path(bundle) == bundle / ".mneme" / "fts.db"
    assert indexlib.l2_index_path(bundle) == bundle / ".mneme" / "l2.db"
    assert indexlib.fts_index_path(bundle) != indexlib.l2_index_path(bundle)
