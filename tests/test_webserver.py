"""Web console (``mneme serve``) endpoint tests.

Spins up the stdlib ``ThreadingHTTPServer`` on an ephemeral port
(``port=0``) against a tmp copy of ``sample-bundle`` and exercises the
spec's security model (token, Host header, path sandbox, body cap) plus
the read endpoints and the single disposable-cache write endpoint (reindex).
"""
from __future__ import annotations

import http.client
import json
import shutil
import threading
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "sample-bundle"


@pytest.fixture()
def server(tmp_path):
    from mneme.webserver import make_server

    bundle = tmp_path / "wiki"
    shutil.copytree(SAMPLE, bundle)
    config_path = tmp_path / "config.toml"
    config_path.write_text(f'bundle_path = "{bundle}"\n', encoding="utf-8")

    httpd, state = make_server(bundle, config_path, host="127.0.0.1", port=0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    port = httpd.server_address[1]
    try:
        yield type(
            "Srv",
            (),
            {
                "port": port,
                "token": state.token,
                "bundle": bundle,
                "config_path": config_path,
                "httpd": httpd,
            },
        )()
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


def _req(server, method, path, *, token="__use_real__", host=None, body=None):
    conn = http.client.HTTPConnection("127.0.0.1", server.port, timeout=10)
    headers = {}
    if token == "__use_real__":
        headers["X-Mneme-Token"] = server.token
    elif token is not None:
        headers["X-Mneme-Token"] = token
    if host is not None:
        headers["Host"] = host
    conn.request(method, path, body=body, headers=headers)
    resp = conn.getresponse()
    raw = resp.read()
    conn.close()
    try:
        payload = json.loads(raw)
    except ValueError:
        payload = None
    return resp.status, payload, raw


# ---------------------------------------------------------------------------
# GET / (index page)
# ---------------------------------------------------------------------------


def test_index_serves_ui_with_injected_token(server):
    status, payload, raw = _req(server, "GET", "/", token=None)
    assert status == 200
    html = raw.decode("utf-8")
    assert "Mneme" in html
    assert 'id="skillVersion"' in html
    assert "'v' + s.version" in html
    assert "Mneme Web UI · v" in html
    assert "__MNEME_TOKEN__" not in html, "token placeholder must be replaced"
    assert server.token in html, "session token must be injected into GET /"
    assert "召回" in html
    assert "distance" in html
    assert "合并、基础、富化分别是什么？" in html
    assert "graphKindFilter" in html
    assert "graphViewFilter" in html
    assert "GRAPH_OVERVIEW_LIMIT" in html
    assert "查看邻域" in html
    assert "graphBackBtn" in html
    assert "graphFullscreenBtn" in html
    assert "graphFocusId" in html
    assert "agent 提取实体" in html
    assert "agent Graph 富化 extraction JSON" in html
    assert "先选最多 5 个有代表性的现有页面做回填试点" in html
    assert "`mneme graph ingest`" in html
    assert "pageGraphContext" in html


def test_unknown_path_is_404(server):
    status, payload, _ = _req(server, "GET", "/nope", token=None)
    assert status == 404
    assert payload["code"] == "not_found"
    assert "error" in payload


# ---------------------------------------------------------------------------
# Token enforcement on /api/*
# ---------------------------------------------------------------------------


def test_api_requires_token(server):
    status, payload, _ = _req(server, "GET", "/api/status", token=None)
    assert status == 401
    assert payload["code"] == "unauthorized"


def test_api_rejects_wrong_token(server):
    status, payload, _ = _req(server, "GET", "/api/status", token="wrong-token")
    assert status == 401
    assert payload["code"] == "unauthorized"


def test_post_requires_token(server):
    status, payload, _ = _req(server, "POST", "/api/reindex", token=None)
    assert status == 401
    assert payload["code"] == "unauthorized"


# ---------------------------------------------------------------------------
# Host header validation
# ---------------------------------------------------------------------------


def test_host_header_must_be_localhost(server):
    status, payload, _ = _req(server, "GET", "/api/status", host="evil.example.com")
    assert status == 403
    assert payload["code"] == "forbidden_host"


def test_host_header_localhost_with_port_ok(server):
    status, _, _ = _req(server, "GET", "/api/status", host=f"localhost:{server.port}")
    assert status == 200


# ---------------------------------------------------------------------------
# Read endpoints
# ---------------------------------------------------------------------------


def test_status_reports_bundle(server):
    status, payload, _ = _req(server, "GET", "/api/status")
    assert status == 200
    assert payload["initialized"] is True
    assert payload["bundle"] == str(server.bundle.resolve())
    assert payload["version"]
    assert payload["pages"]["total"] > 0
    assert set(payload["indexes"]) == {"fts5", "graph", "l2"}
    assert set(payload["lint"]) == {"errors", "warnings"}
    assert isinstance(payload["recent_log"], list)


def test_lint_returns_structured_diagnostics(server):
    status, payload, _ = _req(server, "GET", "/api/lint")
    assert status == 200
    assert isinstance(payload["diagnostics"], list)
    for d in payload["diagnostics"]:
        assert {"severity", "code", "path", "detail"} <= set(d)
    assert isinstance(payload["orphans"], list)
    assert payload["errors"] == sum(
        1 for d in payload["diagnostics"] if d["severity"] == "ERROR"
    )


def test_pages_listing_and_filters(server):
    status, payload, _ = _req(server, "GET", "/api/pages")
    assert status == 200
    pages = payload["pages"]
    assert pages, "sample-bundle should yield pages"
    assert "/sources/karpathy-llm-wiki.md" in {page["path"] for page in pages}
    for p in pages:
        assert p["path"].startswith("/")
        assert "type" in p and "tags" in p and "orphan" in p
    some_type = pages[0]["type"]
    if some_type:
        status2, payload2, _ = _req(server, "GET", f"/api/pages?type={some_type}")
        assert status2 == 200
        assert all(p["type"] == some_type for p in payload2["pages"])


def test_page_referenced_only_by_root_index_is_not_orphan(tmp_path):
    from mneme.webserver import _page_summaries

    bundle = tmp_path / "wiki"
    concept = bundle / "concepts" / "indexed.md"
    concept.parent.mkdir(parents=True)
    concept.write_text(
        "---\ntype: Concept\ntitle: Indexed\ntags: [test]\n---\n\n# Indexed\n",
        encoding="utf-8",
    )
    (bundle / "index.md").write_text(
        "# Index\n\n- [Indexed](/concepts/indexed.md)\n",
        encoding="utf-8",
    )

    pages = _page_summaries(bundle)

    assert pages == [
        {
            "path": "/concepts/indexed.md",
            "title": "Indexed",
            "type": "Concept",
            "tags": ["test"],
            "description": "",
            "timestamp": "",
            "orphan": False,
        }
    ]


def test_page_returns_frontmatter_and_links(server):
    status, payload, _ = _req(server, "GET", "/api/pages")
    target = payload["pages"][0]["path"]
    status, page, _ = _req(server, "GET", f"/api/page?path={target}")
    assert status == 200
    assert page["path"] == target
    assert isinstance(page["frontmatter"], dict)
    assert "raw" in page and "body" in page
    assert isinstance(page["outlinks"], list)
    assert isinstance(page["inlinks"], list)
    assert page["graph"] == {
        "available": False,
        "fresh": False,
        "entities": [],
        "relations": [],
    }


def test_page_missing_is_404(server):
    status, payload, _ = _req(server, "GET", "/api/page?path=/concepts/nope.md")
    assert status == 404
    assert payload["code"] == "not_found"


# ---------------------------------------------------------------------------
# Path sandbox
# ---------------------------------------------------------------------------


def test_page_rejects_dotdot_escape(server):
    status, payload, _ = _req(server, "GET", "/api/page?path=../../pyproject.toml")
    assert status == 403
    assert payload["code"] == "path_escape"


def test_page_rejects_deep_dotdot_md(server):
    status, payload, _ = _req(
        server, "GET", "/api/page?path=../../../../etc/passwd.md"
    )
    assert status == 403
    assert payload["code"] == "path_escape"


def test_page_absolute_path_cannot_escape(server):
    # An absolute-looking path is treated as bundle-relative after the
    # leading slash is stripped, so it can never leave the bundle: the
    # resolution lands inside the bundle and simply does not exist.
    status, payload, _ = _req(server, "GET", "/api/page?path=/etc/passwd")
    assert status in (403, 404)
    assert payload["code"] in ("path_escape", "not_found")


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


def test_search_l0_fallback_without_index(server):
    status, payload, _ = _req(server, "GET", "/api/search?q=okf")
    assert status == 200
    assert payload["query"] == "okf"
    assert payload["candidates"], "L0 grep should find OKF content in sample-bundle"
    for cand in payload["candidates"]:
        assert cand["path"].startswith("/")
        assert {"path", "title", "snippet"} <= set(cand)


def test_search_requires_query(server):
    status, payload, _ = _req(server, "GET", "/api/search")
    assert status == 400
    assert payload["code"] == "bad_request"


def test_search_k_bounds(server):
    status, payload, _ = _req(server, "GET", "/api/search?q=okf&k=0")
    assert status == 400
    status, payload, _ = _req(server, "GET", "/api/search?q=okf&k=101")
    assert status == 400


def test_search_l2_preserves_page_distance(server, monkeypatch):
    from mneme import indexlib

    l2_db = indexlib.l2_index_path(server.bundle)
    l2_db.parent.mkdir(exist_ok=True)
    l2_db.touch()
    monkeypatch.setattr(indexlib, "default_embed_fn", lambda: object())
    monkeypatch.setattr(
        indexlib,
        "search_bundle",
        lambda bundle, query, k, embed_fn: [
            {
                "path": "concepts/example.md",
                "title": "Example",
                "text": "best page chunk",
                "distance": 0.75,
            }
        ],
    )

    status, payload, _ = _req(
        server, "GET", "/api/search?q=example&k=20&mode=l2"
    )

    assert status == 200
    assert payload["mode"] == "l2"
    assert payload["candidates"] == [
        {
            "path": "/concepts/example.md",
            "title": "Example",
            "snippet": "best page chunk",
            "distance": 0.75,
        }
    ]


# ---------------------------------------------------------------------------
# Dream + graph (read-only)
# ---------------------------------------------------------------------------


def test_dream_audit_is_readonly(server):
    before = {
        p: p.read_bytes() for p in server.bundle.rglob("*") if p.is_file()
    }
    status, payload, _ = _req(server, "GET", "/api/dream")
    assert status == 200
    assert "okf_hard_rules" in payload
    assert "mneme_writer_rules" in payload
    after = {p: p.read_bytes() for p in server.bundle.rglob("*") if p.is_file()}
    assert before == after, "dream audit must not modify the bundle"


def test_graph_returns_nodes_and_edges(server):
    status, payload, _ = _req(server, "GET", "/api/graph")
    assert status == 200
    assert payload["available"] is False
    assert isinstance(payload["nodes"], list)
    assert isinstance(payload["edges"], list)
    assert payload["stats"]["nodes"] == len(payload["nodes"])
    assert payload["stats"]["markdown_pages"] > 0


def test_graph_returns_base_and_enriched_layers_with_source_pages(server):
    from mneme import graphlib

    graphlib.rebuild_graph(server.bundle)
    graphlib.ingest_extraction(
        graphlib.graph_index_path(server.bundle),
        {
            "version": 1,
            "pages": [
                {
                    "page": "concepts/llm-wiki.md",
                    "entities": [
                        {
                            "name": "GraphDB",
                            "type": "technology",
                            "description": "Local graph cache",
                            "confidence": 0.9,
                        }
                    ],
                    "relations": [],
                }
            ],
        },
        persist=False,
    )

    status, payload, _ = _req(server, "GET", "/api/graph")
    assert status == 200
    assert payload["available"] is True
    assert payload["fresh"] is True
    assert payload["stats"]["base_nodes"] > 0
    assert payload["stats"]["enriched_nodes"] == 1
    assert payload["stats"]["enriched_edges"] == 1

    entity = next(node for node in payload["nodes"] if node["name"] == "GraphDB")
    assert entity["id"].startswith("entity:")
    assert entity["layer"] == "enriched"
    assert entity["related_pages"] == ["/concepts/llm-wiki.md"]
    mention = next(edge for edge in payload["edges"] if edge["predicate"] == "mentions")
    assert mention["id"].startswith("relation:")
    assert mention["layers"] == ["enriched"]
    assert mention["sources"][0]["page"] == "/concepts/llm-wiki.md"

    status, page, _ = _req(
        server, "GET", "/api/page?path=/concepts/llm-wiki.md"
    )
    assert status == 200
    assert page["graph"]["available"] is True
    assert any(item["name"] == "GraphDB" for item in page["graph"]["entities"])
    assert any(
        item["predicate"] == "mentions" for item in page["graph"]["relations"]
    )


# ---------------------------------------------------------------------------
# POST /api/reindex (only disposable-cache write endpoint)
# ---------------------------------------------------------------------------


def test_reindex_fts_mode_builds_fts_and_graph(server):
    fts_db = server.bundle / ".mneme" / "fts.db"
    graph_db = server.bundle / ".mneme" / "graph.db"
    assert not fts_db.exists()
    assert not graph_db.exists()
    status, payload, _ = _req(server, "POST", "/api/reindex")
    assert status == 200
    assert payload["active_mode"] == "fts5"
    assert payload["l2"] is None
    assert payload["fts_pages"] > 0
    assert payload["graph"]["pages"] > 0
    assert fts_db.is_file()
    assert graph_db.is_file()
    # Idempotent: a second run succeeds too.
    status, _, _ = _req(server, "POST", "/api/reindex")
    assert status == 200


def test_reindex_l2_mode_builds_l2_fts_and_graph(server, monkeypatch):
    from mneme import indexlib
    from mneme.config import write_config

    write_config(
        server.config_path,
        {"bundle_path": str(server.bundle), "active_retrieval_mode": "l2"},
    )
    embedder = indexlib.Embedder(lambda texts: [[0.0] for _ in texts], "test-model")
    monkeypatch.setattr(indexlib, "default_embed_fn", lambda: embedder)

    def fake_reindex(bundle, active_embedder):
        assert active_embedder is embedder
        path = indexlib.l2_index_path(bundle)
        path.parent.mkdir(exist_ok=True)
        path.touch()
        return indexlib.ReindexResult(3, 7, 0, path)

    monkeypatch.setattr(indexlib, "reindex_bundle", fake_reindex)

    status, payload, _ = _req(server, "POST", "/api/reindex")

    assert status == 200
    assert payload["active_mode"] == "l2"
    assert payload["l2"] == {
        "concepts": 3,
        "chunks": 7,
        "skipped": 0,
        "model": "test-model",
    }
    assert payload["fts_pages"] > 0
    assert payload["graph"]["pages"] > 0
    assert indexlib.l2_index_path(server.bundle).is_file()
    assert indexlib.fts_index_path(server.bundle).is_file()
    assert indexlib.graph_index_path(server.bundle).is_file()


def test_reindex_l2_failure_is_explicit_and_stops_rebuild(server, monkeypatch):
    from mneme import indexlib
    from mneme.config import write_config

    write_config(
        server.config_path,
        {"bundle_path": str(server.bundle), "active_retrieval_mode": "l2"},
    )

    def fail_embedder():
        raise indexlib.FastEmbedUnavailableError("fastembed is unavailable")

    monkeypatch.setattr(indexlib, "default_embed_fn", fail_embedder)

    status, payload, _ = _req(server, "POST", "/api/reindex")

    assert status == 500
    assert payload["code"] == "l2_reindex_failed"
    assert payload["error"] == "reindex (L2) failed: fastembed is unavailable"
    assert not indexlib.fts_index_path(server.bundle).exists()
    assert not indexlib.graph_index_path(server.bundle).exists()


def test_reindex_does_not_touch_markdown(server):
    md_before = {
        p: p.read_bytes() for p in server.bundle.rglob("*.md") if p.is_file()
    }
    status, _, _ = _req(server, "POST", "/api/reindex")
    assert status == 200
    md_after = {
        p: p.read_bytes() for p in server.bundle.rglob("*.md") if p.is_file()
    }
    assert md_before == md_after, "reindex must only rebuild .mneme/ caches"


def test_post_unknown_endpoint_is_404(server):
    status, payload, _ = _req(server, "POST", "/api/dream/apply")
    assert status == 404


def test_post_body_over_1mb_rejected(server):
    big = b"x" * (1024 * 1024 + 1)
    status, payload, _ = _req(server, "POST", "/api/reindex", body=big)
    assert status == 413
    assert payload["code"] == "payload_too_large"


# ---------------------------------------------------------------------------
# Uninitialized bundle -> graceful empty state
# ---------------------------------------------------------------------------


def test_uninitialized_bundle_serves_guide_state(tmp_path):
    from mneme.webserver import make_server

    bundle = tmp_path / "empty-wiki"
    bundle.mkdir()
    httpd, state = make_server(bundle, tmp_path / "config.toml", port=0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    fake = type("Srv", (), {"port": httpd.server_address[1], "token": state.token})()
    try:
        status, payload, _ = _req(fake, "GET", "/api/status")
        assert status == 200
        assert payload["initialized"] is False
        assert payload["pages"]["total"] == 0
        status, payload, _ = _req(fake, "GET", "/api/lint")
        assert status == 200
        assert payload["diagnostics"] == []
        status, payload, _ = _req(fake, "GET", "/api/search?q=x")
        assert status == 200
        assert payload["candidates"] == []
        status, payload, _ = _req(fake, "POST", "/api/reindex")
        assert status == 409
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)
