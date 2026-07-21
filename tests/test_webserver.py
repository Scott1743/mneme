"""P1 web console (``mneme serve``) endpoint tests.

Spins up the stdlib ``ThreadingHTTPServer`` on an ephemeral port
(``port=0``) against a tmp copy of ``sample-bundle`` and exercises the
spec's security model (token, Host header, path sandbox, body cap) plus
the P1 read endpoints and the single write endpoint (reindex).
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
    assert "__MNEME_TOKEN__" not in html, "token placeholder must be replaced"
    assert server.token in html, "session token must be injected into GET /"


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
    for p in pages:
        assert p["path"].startswith("/")
        assert "type" in p and "tags" in p and "orphan" in p
    some_type = pages[0]["type"]
    if some_type:
        status2, payload2, _ = _req(server, "GET", f"/api/pages?type={some_type}")
        assert status2 == 200
        assert all(p["type"] == some_type for p in payload2["pages"])


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
    assert isinstance(payload["nodes"], list)
    assert isinstance(payload["edges"], list)
    assert payload["stats"]["nodes"] == len(payload["nodes"])


# ---------------------------------------------------------------------------
# POST /api/reindex (only P1 write endpoint)
# ---------------------------------------------------------------------------


def test_reindex_builds_fts_cache(server):
    fts_db = server.bundle / ".mneme" / "fts.db"
    assert not fts_db.exists()
    status, payload, _ = _req(server, "POST", "/api/reindex")
    assert status == 200
    assert payload["fts_pages"] > 0
    assert fts_db.is_file()
    # Idempotent: a second run succeeds too.
    status, _, _ = _req(server, "POST", "/api/reindex")
    assert status == 200


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
