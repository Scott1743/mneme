"""v4 Phase 1 graph index and hybrid retrieval tests."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

import mneme
from mneme import graphlib, indexlib

pytestmark = pytest.mark.unit


def _bundle(tmp_path: Path) -> Path:
    bundle = tmp_path / "wiki"
    (bundle / "concepts").mkdir(parents=True)
    (bundle / "concepts" / "alpha.md").write_text(
        "---\n"
        "type: Concept\n"
        "title: Alpha\n"
        "description: Alpha uses Beta\n"
        "tags: [graph, shared]\n"
        "timestamp: 2026-07-20T00:00:00Z\n"
        "---\n"
        "Alpha body mentions graph systems.\n"
        "See [Beta](/concepts/beta.md).\n",
        encoding="utf-8",
    )
    (bundle / "concepts" / "beta.md").write_text(
        "---\n"
        "type: Concept\n"
        "title: Beta\n"
        "description: Beta page\n"
        "tags: [shared]\n"
        "timestamp: 2026-07-20T00:00:00Z\n"
        "---\n"
        "Beta contains a distinctive needle.\n",
        encoding="utf-8",
    )
    (bundle / "index.md").write_text(
        '---\nokf_version: "0.1"\n---\n\n# Concepts\n', encoding="utf-8"
    )
    (bundle / "log.md").write_text("# Directory Update Log\n", encoding="utf-8")
    return bundle


def test_graph_schema_contains_v4_tables_and_indexes():
    conn = sqlite3.connect(":memory:")
    try:
        graphlib.ensure_graph_schema(conn)
        tables = {
            row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert {"entities", "relations", "entity_embeddings", "communities", "meta"} <= tables
        indexes = {
            row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            )
        }
        assert "idx_relations_pred_obj" in indexes
    finally:
        conn.close()


def test_rebuild_graph_extracts_pages_tags_and_links(tmp_path):
    bundle = _bundle(tmp_path)
    result = graphlib.rebuild_graph(bundle)
    assert result.indexed_pages == 2
    assert result.indexed_entities == 4  # two pages + graph/shared tags
    assert result.indexed_relations == 4  # three tagged_by + one relates_to
    assert result.db_path == bundle / ".mneme" / "graph.db"

    conn = graphlib.open_graph(result.db_path)
    try:
        predicates = {
            row[0]: row[1]
            for row in conn.execute(
                "SELECT predicate, COUNT(*) FROM relations GROUP BY predicate"
            )
        }
        assert predicates == {"relates_to": 1, "tagged_by": 3}
        assert dict(conn.execute("SELECT key, value FROM meta"))["schema_version"] == "1"
    finally:
        conn.close()


def test_graph_search_walks_from_tag_to_related_pages(tmp_path):
    bundle = _bundle(tmp_path)
    graphlib.rebuild_graph(bundle)
    out = graphlib.search_graph(graphlib.graph_index_path(bundle), "shared", k=10)
    assert [item["path"] for item in out["candidates"]] == [
        "concepts/alpha.md",
        "concepts/beta.md",
    ]
    assert all("graph_context" in item for item in out["candidates"])


def test_hybrid_search_fuses_graph_and_fts(tmp_path):
    bundle = _bundle(tmp_path)
    paths = sorted((bundle / "concepts").glob("*.md"))
    assert indexlib.reindex_paths(paths, bundle) == 2
    graphlib.rebuild_graph(bundle)

    out = indexlib.search_hybrid(bundle, "needle", k=5)
    assert out["graph_context"]["mode"] == "hybrid"
    assert out["candidates"][0]["path"] == "concepts/beta.md"
    assert "needle" in out["candidates"][0]["snippet"]
    assert out["candidates"][0]["score"] > 0


def test_hybrid_search_falls_back_to_fts_without_graph(tmp_path):
    bundle = _bundle(tmp_path)
    paths = sorted((bundle / "concepts").glob("*.md"))
    indexlib.reindex_paths(paths, bundle)

    out = indexlib.search_hybrid(bundle, "needle", k=5)
    assert out["candidates"][0]["path"] == "concepts/beta.md"
    assert out["graph_context"]["fallback"] == "fts5"


def test_cli_reindex_graph_and_search_modes(tmp_path, capsys):
    bundle = _bundle(tmp_path)
    cfg = tmp_path / "config.toml"
    cfg.write_text(f'bundle_path = "{bundle}"\n', encoding="utf-8")

    assert mneme.main(["reindex", "--graph", "--config", str(cfg)]) == 0
    assert graphlib.graph_index_path(bundle).is_file()
    assert indexlib.fts_index_path(bundle).is_file()
    assert "entity(s)" in capsys.readouterr().out

    assert mneme.main(
        ["search", "shared", "--mode", "graph", "--json", "--config", str(cfg)]
    ) == 0
    payload = json.loads(capsys.readouterr().out)
    assert {item["path"] for item in payload["candidates"]} == {
        "concepts/alpha.md",
        "concepts/beta.md",
    }

    assert mneme.main(
        ["search", "needle", "--mode", "hybrid", "--json", "--config", str(cfg)]
    ) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["candidates"][0]["path"] == "concepts/beta.md"


def test_dream_json_reports_graph_health_without_writing(tmp_path, capsys):
    bundle = _bundle(tmp_path)
    graphlib.rebuild_graph(bundle)
    before = {
        path.relative_to(bundle).as_posix(): path.read_bytes()
        for path in bundle.rglob("*")
        if path.is_file()
    }

    assert mneme.main(["dream", "--bundle", str(bundle), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["graph"]["entity_count"] == 4
    assert payload["graph"]["relation_count"] == 4
    after = {
        path.relative_to(bundle).as_posix(): path.read_bytes()
        for path in bundle.rglob("*")
        if path.is_file()
    }
    assert after == before
