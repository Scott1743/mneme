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
        assert dict(conn.execute("SELECT key, value FROM meta"))["schema_version"] == "3"
    finally:
        conn.close()


def test_rebuild_graph_includes_okf_source_pages(tmp_path):
    bundle = _bundle(tmp_path)
    (bundle / "sources").mkdir()
    (bundle / "sources" / "paper.md").write_text(
        "---\ntype: Source\ntitle: Paper\ndescription: Provenance page\n"
        "tags: [source]\ntimestamp: 2026-07-22\n"
        "resource: /raw-sources/paper.md.raw\n---\nSource body.\n",
        encoding="utf-8",
    )

    result = graphlib.rebuild_graph(bundle)

    assert result.indexed_pages == 3
    conn = graphlib.open_graph(result.db_path)
    try:
        assert conn.execute(
            "SELECT COUNT(*) FROM entities WHERE page_path='sources/paper.md'"
        ).fetchone()[0] == 1
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


def test_hybrid_search_fuses_graph_recalled_pages_with_fts_rank(tmp_path):
    """Exercise the graph+FTS5 fusion path (not the FTS5 fallback).

    Querying a tag name ("shared") hits the tag entity, BFS reaches both
    pages tagged with it, and FTS5 then ranks those candidates. This is
    the only test that executes ``search_hybrid`` lines 700-756.
    """
    bundle = _bundle(tmp_path)
    paths = sorted((bundle / "concepts").glob("*.md"))
    indexlib.reindex_paths(paths, bundle)
    graphlib.rebuild_graph(bundle)

    out = indexlib.search_hybrid(bundle, "shared", k=5)
    assert out["graph_context"]["mode"] == "hybrid"
    assert "fallback" not in out["graph_context"]
    assert out["graph_context"]["graph_candidates"] >= 2

    paths_returned = {item["path"] for item in out["candidates"]}
    assert paths_returned == {"concepts/alpha.md", "concepts/beta.md"}

    for candidate in out["candidates"]:
        assert candidate["graph_score"] > 0
        assert "fts_score" in candidate
        assert "score" in candidate
        assert candidate["graph_context"]["distance"] is not None
        assert isinstance(candidate["graph_context"]["matched_entities"], list)


def test_hybrid_unions_global_fts_hits_with_graph_candidates(tmp_path):
    bundle = _bundle(tmp_path)
    (bundle / "concepts" / "gamma.md").write_text(
        "---\ntype: Concept\ntitle: Gamma\ndescription: needle graph seed\n"
        "tags: [isolated]\n---\nNo lexical target here.\n",
        encoding="utf-8",
    )
    paths = sorted((bundle / "concepts").glob("*.md"))
    indexlib.reindex_paths(paths, bundle)
    graphlib.rebuild_graph(bundle)

    out = indexlib.search_hybrid(bundle, "needle", k=10)

    returned = {item["path"] for item in out["candidates"]}
    assert "concepts/gamma.md" in returned  # graph seed
    assert "concepts/beta.md" in returned  # global FTS-only hit
    # FTS5 searches globally instead of being restricted to graph candidates.
    assert out["graph_context"]["fts_candidates"] >= 1


def test_hybrid_falls_back_to_global_fts_when_graph_is_stale(tmp_path):
    bundle = _bundle(tmp_path)
    paths = sorted((bundle / "concepts").glob("*.md"))
    indexlib.reindex_paths(paths, bundle)
    graphlib.rebuild_graph(bundle)
    assert graphlib.graph_is_fresh(bundle)

    (bundle / "concepts" / "beta.md").write_text(
        (bundle / "concepts" / "beta.md").read_text(encoding="utf-8")
        + "\nFresh lexical marker.\n",
        encoding="utf-8",
    )
    indexlib.reindex_paths(paths, bundle)
    assert not graphlib.graph_is_fresh(bundle)

    out = indexlib.search_hybrid(bundle, "marker", k=5)
    assert out["candidates"][0]["path"] == "concepts/beta.md"
    assert out["graph_context"]["reason"] == "graph index is stale"


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


def test_rebuild_graph_skips_non_utf8_file_without_failing(tmp_path):
    """OKF §9 tolerance: a non-UTF-8 file must not break the whole rebuild."""
    bundle = _bundle(tmp_path)
    (bundle / "concepts" / "broken.md").write_bytes(
        b"---\ntype: Concept\ntitle: Broken\n---\n\xff\xfe invalid utf8\n"
    )

    result = graphlib.rebuild_graph(bundle)

    # The two well-formed pages must still be indexed; only the bad one is skipped.
    assert result.indexed_pages == 2
    valid_paths = {
        row[0]
        for row in graphlib.open_graph(result.db_path).execute(
            "SELECT page_path FROM entities WHERE entity_type=?",
            (graphlib.PAGE_ENTITY_TYPE,),
        )
    }
    assert "concepts/alpha.md" in valid_paths
    assert "concepts/beta.md" in valid_paths
    assert "concepts/broken.md" not in valid_paths


def test_find_entity_by_name_matches_description_field(tmp_path):
    """Graph search must surface entities whose ``description`` mentions the
    query even when the name and properties do not.

    Regression guard for v4.0.1: ``find_entity_by_name`` previously omitted
    the ``description`` column from its WHERE clause, so pages whose name is
    a path/slug but whose description carries the semantic content (the
    common case for bootstrap dogfood pages) were never returned.
    """
    bundle = _bundle(tmp_path)
    graphlib.rebuild_graph(bundle)
    conn = graphlib.open_graph(graphlib.graph_index_path(bundle))
    try:
        # "alpha" appears only in description ("Alpha uses Beta"), not in
        # any page name (which is "concepts/alpha.md") or properties JSON.
        hits = graphlib.find_entity_by_name(conn, "alpha", limit=10)
        assert hits, "find_entity_by_name must match the description column"
        assert any(h["page_path"] == "concepts/alpha.md" for h in hits)
    finally:
        conn.close()


def test_full_query_description_outranks_incidental_token_match(tmp_path):
    bundle = _bundle(tmp_path)
    rebuilt = graphlib.rebuild_graph(bundle)
    query = "automatic process with AI"
    graphlib.ingest_extraction(
        rebuilt.db_path,
        {
            "version": 1,
            "pages": [
                {
                    "page": "concepts/alpha.md",
                    "entities": [{
                        "name": "Workflow",
                        "type": "process",
                        "description": query,
                        "confidence": 0.9,
                    }],
                    "relations": [],
                },
                {
                    "page": "concepts/beta.md",
                    "entities": [{
                        "name": "AI",
                        "type": "technology",
                        "description": "generic token match",
                        "confidence": 0.9,
                    }],
                    "relations": [],
                },
            ],
        },
        persist=False,
    )

    conn = graphlib.open_graph(rebuilt.db_path)
    try:
        hits = graphlib.find_entity_by_name(conn, query, limit=10)
    finally:
        conn.close()
    assert hits[0]["name"] == "Workflow"
    assert hits[0]["_match_score"] == pytest.approx(0.95)

    candidates = graphlib.graph_page_candidates(rebuilt.db_path, query, limit=10)
    assert candidates[0]["page_path"] == "concepts/alpha.md"
    assert candidates[0]["graph_score"] == pytest.approx(0.95 * 0.9 * 0.8)


def test_search_graph_returns_candidates_via_description_match(tmp_path):
    """End-to-end graph search must return a page when only its description
    matches the query (the v4.0.0 release returned 0 candidates for this
    case against the real dogfood corpus).
    """
    bundle = _bundle(tmp_path)
    graphlib.rebuild_graph(bundle)
    out = graphlib.search_graph(graphlib.graph_index_path(bundle), "alpha", k=5)
    paths = [item["path"] for item in out["candidates"]]
    assert "concepts/alpha.md" in paths


def test_hybrid_search_uses_graph_recall_when_query_hits_description(tmp_path):
    """``search_hybrid`` should use graph-recalled pages (reached via a
    description match) as the candidate set for FTS5 re-ranking. Without
    the description column in ``find_entity_by_name``, the graph leg would
    return nothing and hybrid would silently fall back to global FTS5.
    """
    bundle = _bundle(tmp_path)
    paths = sorted((bundle / "concepts").glob("*.md"))
    indexlib.reindex_paths(paths, bundle)
    graphlib.rebuild_graph(bundle)

    out = indexlib.search_hybrid(bundle, "alpha", k=5)
    assert out["graph_context"]["mode"] == "hybrid"
    # Graph recalled at least one page via description.
    assert out["graph_context"]["graph_candidates"] >= 1
    assert "concepts/alpha.md" in {c["path"] for c in out["candidates"]}


# ---------------------------------------------------------------------------
# v4 Phase 2: agent extraction ingest
# ---------------------------------------------------------------------------


def _extraction_payload() -> dict:
    return {
        "version": 1,
        "pages": [
            {
                "page": "concepts/alpha.md",
                "entities": [
                    {"name": "GraphDB", "type": "technology", "description": "图数据库", "confidence": 0.9},
                    {"name": "Needle 引擎", "type": "product", "description": "", "confidence": 0.8},
                ],
                "relations": [
                    {
                        "subject": "Alpha",
                        "predicate": "uses",
                        "object": "GraphDB",
                        "confidence": 0.85,
                        "evidence": "Alpha body mentions graph systems.",
                    }
                ],
            }
        ],
    }


def test_schema_upgrade_adds_provenance_columns(tmp_path):
    """v1 databases upgrade in place to v2 with provenance columns."""
    bundle = _bundle(tmp_path)
    result = graphlib.rebuild_graph(bundle)
    conn = graphlib.open_graph(result.db_path)
    try:
        entity_cols = {row[1] for row in conn.execute("PRAGMA table_info(entities)")}
        relation_cols = {row[1] for row in conn.execute("PRAGMA table_info(relations)")}
        assert {"source", "confidence"} <= entity_cols
        assert {"source", "confidence", "evidence"} <= relation_cols
        # Deterministic rebuild tags provenance.
        sources = {
            row[0] for row in conn.execute("SELECT DISTINCT source FROM entities")
        }
        assert sources == {graphlib.ENTITY_SOURCE_PAGE, graphlib.ENTITY_SOURCE_TAG}
        rel_sources = {
            row[0] for row in conn.execute("SELECT DISTINCT source FROM relations")
        }
        assert rel_sources == {graphlib.REL_SOURCE_TAG, graphlib.REL_SOURCE_LINK}
    finally:
        conn.close()


def test_ingest_extraction_adds_entities_relations_and_mentions(tmp_path):
    bundle = _bundle(tmp_path)
    result = graphlib.rebuild_graph(bundle)
    ingest = graphlib.ingest_extraction(result.db_path, _extraction_payload())

    assert ingest.pages_ingested == 1
    assert ingest.entities_upserted == 3  # GraphDB + Needle 引擎 + Alpha (relation subject)
    # 2 entity mentions + 1 subject mention + 1 uses relation.
    assert ingest.relations_upserted == 4
    assert ingest.warnings == ()

    conn = graphlib.open_graph(result.db_path)
    try:
        row = conn.execute(
            "SELECT source, confidence, description FROM entities WHERE name=? AND entity_type=?",
            ("GraphDB", "technology"),
        ).fetchone()
        assert row is not None
        assert row[0] == graphlib.ENTITY_SOURCE_LLM
        assert row[1] == pytest.approx(0.9)
        assert row[2] == "图数据库"

        rel = conn.execute(
            """
            SELECT r.predicate, r.source, r.confidence, r.evidence
            FROM relations r
            JOIN entities s ON s.id=r.subject_id
            JOIN entities o ON o.id=r.object_id
            WHERE s.name='Alpha' AND o.name='GraphDB'
            """
        ).fetchone()
        assert rel is not None
        assert rel[0] == "uses"
        assert rel[1] == graphlib.REL_SOURCE_LLM
        assert rel[2] == pytest.approx(0.85)
        assert "graph systems" in rel[3]

        # Page -> entity mentions edge exists so BFS reaches the page.
        page_id = conn.execute(
            "SELECT id FROM entities WHERE page_path=?", ("concepts/alpha.md",)
        ).fetchone()[0]
        gdb_id = conn.execute(
            "SELECT id FROM entities WHERE name='GraphDB'"
        ).fetchone()[0]
        mention = conn.execute(
            "SELECT predicate, source FROM relations WHERE subject_id=? AND object_id=?",
            (page_id, gdb_id),
        ).fetchone()
        assert mention is not None
        assert mention[0] == graphlib.MENTIONS_PREDICATE
        assert mention[1] == graphlib.REL_SOURCE_LLM
    finally:
        conn.close()


def test_graph_snapshot_exposes_both_layers_and_authoritative_pages(tmp_path):
    bundle = _bundle(tmp_path)
    result = graphlib.rebuild_graph(bundle)
    graphlib.ingest_extraction(result.db_path, _extraction_payload(), persist=False)

    snapshot = graphlib.graph_snapshot(result.db_path)
    graph_db = next(node for node in snapshot["nodes"] if node["name"] == "GraphDB")
    assert graph_db["kind"] == "entity"
    assert graph_db["layer"] == "enriched"
    assert graph_db["confidence"] == pytest.approx(0.9)
    assert graph_db["related_pages"] == ["concepts/alpha.md"]

    alpha = next(
        node for node in snapshot["nodes"] if node["page_path"] == "concepts/alpha.md"
    )
    assert alpha["kind"] == "page"
    assert alpha["layer"] == "base"

    uses = next(edge for edge in snapshot["edges"] if edge["predicate"] == "uses")
    assert uses["layers"] == ["enriched"]
    assert uses["confidence"] == pytest.approx(0.85)
    assert uses["evidence"] == "Alpha body mentions graph systems."
    assert uses["sources"] == [
        {
            "page": "concepts/alpha.md",
            "source": "llm_extracted",
            "confidence": pytest.approx(0.85),
            "evidence": "Alpha body mentions graph systems.",
        }
    ]

    base_edge = next(edge for edge in snapshot["edges"] if "base" in edge["layers"])
    assert base_edge["sources"]


def test_relation_query_prioritizes_its_evidence_page(tmp_path):
    bundle = _bundle(tmp_path)
    rebuilt = graphlib.rebuild_graph(bundle)
    graphlib.ingest_extraction(rebuilt.db_path, _extraction_payload(), persist=False)

    conn = graphlib.open_graph(rebuilt.db_path)
    try:
        evidence = graphlib.find_relation_evidence(conn, "Alpha uses GraphDB")
    finally:
        conn.close()
    assert evidence["concepts/alpha.md"]["score"] == pytest.approx(0.85)

    out = graphlib.search_graph(rebuilt.db_path, "Alpha uses GraphDB", k=5)
    assert out["candidates"][0]["path"] == "concepts/alpha.md"
    assert "Alpha uses GraphDB" in out["candidates"][0]["graph_context"]["matched_entities"]


def test_ingest_makes_extracted_entity_reachable_from_graph_search(tmp_path):
    """The core Phase-2 payoff: querying an extracted entity name surfaces
    the page that mentions it, even though the page itself never contains
    the term (description/name/properties all miss it)."""
    bundle = _bundle(tmp_path)
    result = graphlib.rebuild_graph(bundle)
    # Before ingest: "GraphDB" hits nothing.
    before = graphlib.search_graph(result.db_path, "GraphDB", k=5)
    assert before["candidates"] == []

    graphlib.ingest_extraction(result.db_path, _extraction_payload())
    after = graphlib.search_graph(result.db_path, "GraphDB", k=5)
    paths = [item["path"] for item in after["candidates"]]
    assert "concepts/alpha.md" in paths


def test_ingest_is_idempotent_per_page(tmp_path):
    bundle = _bundle(tmp_path)
    result = graphlib.rebuild_graph(bundle)
    graphlib.ingest_extraction(result.db_path, _extraction_payload())
    first = graphlib.ingest_extraction(result.db_path, _extraction_payload())
    second_counts = graphlib.graph_health(result.db_path)
    assert second_counts["llm_entity_count"] == 3
    # mentions(3) + uses(1) — no duplication on re-ingest.
    assert second_counts["llm_relation_count"] == 4
    assert first.pages_ingested == 1


def test_graph_rebuild_replays_persisted_extraction(tmp_path):
    bundle = _bundle(tmp_path)
    result = graphlib.rebuild_graph(bundle)
    graphlib.ingest_extraction(result.db_path, _extraction_payload())
    assert graphlib.graph_extraction_path(bundle).is_file()

    rebuilt = graphlib.rebuild_graph(bundle)
    out = graphlib.search_graph(rebuilt.db_path, "GraphDB", k=5)

    assert "concepts/alpha.md" in {item["path"] for item in out["candidates"]}
    assert graphlib.graph_health(rebuilt.db_path)["llm_relation_count"] == 4


def test_shared_extracted_relation_keeps_independent_source_pages(tmp_path):
    bundle = _bundle(tmp_path)
    result = graphlib.rebuild_graph(bundle)
    payload = _extraction_payload()
    second = json.loads(json.dumps(payload["pages"][0]))
    second["page"] = "concepts/beta.md"
    payload["pages"].append(second)
    graphlib.ingest_extraction(result.db_path, payload)

    conn = graphlib.open_graph(result.db_path)
    try:
        supports = conn.execute(
            """
            SELECT COUNT(*) FROM relation_sources rs
            JOIN relations r ON r.id=rs.relation_id
            JOIN entities s ON s.id=r.subject_id
            JOIN entities o ON o.id=r.object_id
            WHERE s.name='Alpha' AND r.predicate='uses' AND o.name='GraphDB'
            """
        ).fetchone()[0]
        assert supports == 2
    finally:
        conn.close()

    replacement = _extraction_payload()
    replacement["pages"][0]["relations"] = []
    graphlib.ingest_extraction(result.db_path, replacement)
    conn = graphlib.open_graph(result.db_path)
    try:
        supports = conn.execute(
            """
            SELECT COUNT(*) FROM relation_sources rs
            JOIN relations r ON r.id=rs.relation_id
            JOIN entities s ON s.id=r.subject_id
            JOIN entities o ON o.id=r.object_id
            WHERE s.name='Alpha' AND r.predicate='uses' AND o.name='GraphDB'
            """
        ).fetchone()[0]
        assert supports == 1
    finally:
        conn.close()


def test_graph_resolves_relative_markdown_links_from_source_directory(tmp_path):
    bundle = _bundle(tmp_path)
    alpha = bundle / "concepts" / "alpha.md"
    alpha.write_text(
        alpha.read_text(encoding="utf-8").replace(
            "[Beta](/concepts/beta.md)", "[Beta](beta.md)"
        ),
        encoding="utf-8",
    )

    result = graphlib.rebuild_graph(bundle)
    conn = graphlib.open_graph(result.db_path)
    try:
        target = conn.execute(
            "SELECT properties FROM entities WHERE page_path='concepts/beta.md'"
        ).fetchone()
        assert target is not None
        assert json.loads(target[0])["missing"] is False
    finally:
        conn.close()


def test_ingest_skips_unknown_page_and_tolerates_bad_blocks(tmp_path):
    bundle = _bundle(tmp_path)
    result = graphlib.rebuild_graph(bundle)
    payload = {
        "version": 1,
        "pages": [
            {"page": "concepts/ghost.md", "entities": [{"name": "X"}], "relations": []},
            {"page": "concepts/alpha.md", "entities": [{"name": "Valid", "type": "concept"}], "relations": []},
            "not-an-object",
            {"page": 42},
        ],
    }
    ingest = graphlib.ingest_extraction(result.db_path, payload)
    assert ingest.pages_ingested == 1
    assert any("ghost" in w for w in ingest.warnings)
    assert any("not an object" in w for w in ingest.warnings)
    assert any("invalid page" in w for w in ingest.warnings)


def test_ingest_rejects_missing_graph(tmp_path):
    bundle = _bundle(tmp_path)
    with pytest.raises(FileNotFoundError):
        graphlib.ingest_extraction(graphlib.graph_index_path(bundle), _extraction_payload())


def test_validate_extraction_normalizes_predicates_and_confidence():
    pages, warnings = graphlib.validate_extraction(
        {
            "version": 1,
            "pages": [
                {
                    "page": "/concepts/alpha.md",
                    "entities": [{"name": "A", "confidence": 3.7}],
                    "relations": [
                        {"subject": "A", "predicate": "Based On!", "object": "B", "confidence": "0.7"},
                        {"subject": "A", "object": "A"},  # self-loop dropped
                        {"subject": "", "object": "B"},   # empty subject dropped
                    ],
                }
            ],
        }
    )
    assert len(warnings) == 2  # self-loop + empty subject, both skipped with warnings
    assert all("skipped" in w for w in warnings)
    assert pages[0]["page"] == "concepts/alpha.md"  # leading slash stripped
    assert pages[0]["entities"][0]["confidence"] == pytest.approx(1.0)
    assert len(pages[0]["relations"]) == 1
    assert pages[0]["relations"][0]["predicate"] == "based_on"
    assert pages[0]["relations"][0]["confidence"] == pytest.approx(0.7)


def test_cli_graph_ingest_from_file_and_stdin(tmp_path, capsys, monkeypatch):
    import io

    bundle = _bundle(tmp_path)
    cfg = tmp_path / "config.toml"
    cfg.write_text(f'bundle_path = "{bundle}"\n', encoding="utf-8")
    assert mneme.main(["reindex", "--graph", "--config", str(cfg)]) == 0
    capsys.readouterr()

    extraction = tmp_path / "extraction.json"
    extraction.write_text(json.dumps(_extraction_payload()), encoding="utf-8")
    assert mneme.main(["graph", "ingest", str(extraction), "--config", str(cfg)]) == 0
    out = capsys.readouterr().out
    assert "ingested 1 page block(s)" in out

    # stdin path.
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(_extraction_payload())))
    assert mneme.main(["graph", "ingest", "-", "--config", str(cfg)]) == 0
    assert "<stdin>" in capsys.readouterr().out

    health = graphlib.graph_health(graphlib.graph_index_path(bundle))
    assert health["llm_entity_count"] == 3
    assert health["llm_relation_count"] == 4
