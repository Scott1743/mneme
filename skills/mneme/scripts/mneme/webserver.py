"""``mneme serve`` — localhost-only, stdlib-only web console (P1).

Design contract: ``docs/design/webserver-prototype.md``.

P1 scope is **read-only + disposable-cache rebuild**:

- ``GET /`` serves the single-file UI (``webui.INDEX_HTML``) with a
  per-process session token injected.
- ``GET /api/*`` endpoints serialize ``okflib`` / ``indexlib`` /
  ``graphlib`` / ``dream`` results as JSON.
- ``POST /api/reindex`` is the ONLY write endpoint; it rebuilds the
  disposable ``.mneme/`` caches (FTS5 always, Graph when present) and
  never touches Markdown. Factual-body writes (dream apply) are P2 and
  intentionally NOT implemented here.

Security model (spec §7):

1. Default bind is ``127.0.0.1``; ``--host 0.0.0.0`` prints a loud warning.
2. A random session token (``secrets.token_urlsafe``) is printed to the
   terminal at startup and injected into ``GET /``; every ``/api/*``
   request — including GETs — must carry a matching ``X-Mneme-Token``
   header.
3. The ``Host`` header must name localhost / 127.0.0.1 / ::1 (DNS
   rebinding mitigation).
4. Page paths resolve inside the bundle; ``..`` escapes and absolute
   paths are rejected.
5. Request bodies are capped at 1 MB; no cookies, no static file
   serving outside ``GET /``.

Process model: foreground ``ThreadingHTTPServer``; Ctrl-C exits
gracefully. No daemonizing, no pidfile.
"""
from __future__ import annotations

import json
import re
import secrets
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, unquote, urlparse

from . import __version__
from .webui import INDEX_HTML

MAX_BODY_BYTES = 1 * 1024 * 1024  # 1 MB request-body cap (spec §7.4)

_HOST_ALLOWLIST = frozenset({"localhost", "127.0.0.1", "::1", "[::1]"})
_WILDCARD_HOSTS = frozenset({"0.0.0.0", "::", ""})

_LINK_RE = re.compile(r"\]\((/[^)\s]+\.md)\)")

_RESERVED = ("index.md", "log.md")
_SKIP_DIRS = (".mneme", "sources", "external-sources")


class ApiError(Exception):
    """HTTP-level error rendered as ``{"error", "code"}``."""

    def __init__(self, status: int, message: str, code: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message
        self.code = code


class ServeState:
    """Per-process server state. Holds no derived data of its own —
    every request reads the bundle / ``.mneme/`` caches fresh."""

    def __init__(
        self,
        bundle: Optional[Path],
        config_path: Path,
        host: str,
        token: Optional[str] = None,
    ) -> None:
        self.bundle = Path(bundle).resolve() if bundle else None
        self.config_path = Path(config_path)
        self.host = host
        self.token = token or secrets.token_urlsafe(24)

    @property
    def initialized(self) -> bool:
        return bool(
            self.bundle
            and self.bundle.is_dir()
            and (self.bundle / "index.md").is_file()
        )


# ---------------------------------------------------------------------------
# Bundle scanning helpers (read-only)
# ---------------------------------------------------------------------------


def _iter_page_files(bundle: Path) -> List[Path]:
    """Non-reserved, non-``.mneme``/``sources`` Markdown files, sorted."""
    out: List[Path] = []
    for p in sorted(bundle.rglob("*.md")):
        if not p.is_file():
            continue
        rel = p.relative_to(bundle)
        if any(part in _SKIP_DIRS for part in rel.parts):
            continue
        if len(rel.parts) == 1 and rel.name in _RESERVED:
            continue
        out.append(p)
    return out


def _page_summaries(bundle: Path) -> List[Dict[str, Any]]:
    """Frontmatter summaries + link-derived orphan flags for every page."""
    from . import okflib

    pages: List[Dict[str, Any]] = []
    texts: Dict[str, str] = {}
    for p in _iter_page_files(bundle):
        rel = "/" + p.relative_to(bundle).as_posix()
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        texts[rel] = text
        parsed = okflib.parse_frontmatter(text)
        meta: Dict[str, Any] = parsed[0] if parsed else {}
        tags = meta.get("tags")
        if not isinstance(tags, list):
            tags = [tags] if isinstance(tags, str) and tags else []
        pages.append(
            {
                "path": rel,
                "title": str(meta.get("title", "") or ""),
                "type": str(meta.get("type", "") or ""),
                "tags": [str(t) for t in tags],
                "description": str(meta.get("description", "") or ""),
                "timestamp": str(meta.get("timestamp", "") or ""),
            }
        )

    inbound: Dict[str, int] = {page["path"]: 0 for page in pages}
    for rel, text in texts.items():
        for target in dict.fromkeys(_LINK_RE.findall(text)):
            if target != rel and target in inbound:
                inbound[target] += 1
    for page in pages:
        page["orphan"] = inbound.get(page["path"], 0) == 0
    return pages


def _page_links(bundle: Path, page_rel: str) -> Tuple[List[str], List[str]]:
    """Outlinks / inlinks for one page, computed from Markdown links.

    Graph Phase 1 derives its page-link edges from the same Markdown
    links, so this file-derived view matches ``graph.db`` for the P1
    browse page while staying available when no graph index exists.
    """
    pages = _page_summaries(bundle)
    known = {p["path"] for p in pages}
    outlinks: List[str] = []
    inlinks: List[str] = []
    for p in pages:
        try:
            text = (bundle / p["path"].lstrip("/")).read_text(
                encoding="utf-8", errors="replace"
            )
        except OSError:
            continue
        targets = dict.fromkeys(_LINK_RE.findall(text))
        if p["path"] == page_rel:
            outlinks = sorted(set(targets))
        elif page_rel in targets:
            inlinks.append(p["path"])
    return sorted(set(outlinks)), sorted(inlinks)


def _recent_log(bundle: Path, limit: int = 5) -> List[str]:
    """Newest ``## `` headings from ``log.md`` (newest-first file)."""
    log_path = bundle / "log.md"
    if not log_path.is_file():
        return []
    try:
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    entries = [ln[3:].strip() for ln in lines if ln.startswith("## ")]
    return entries[:limit]


def _lint_payload(bundle: Path) -> Dict[str, Any]:
    from . import okflib

    report = okflib.lint_bundle(bundle, require_tags=True)
    diagnostics = report.get("diagnostics", [])
    orphan_slugs = okflib.find_orphans(bundle)
    slug_set = set(orphan_slugs)
    orphan_paths = [
        "/" + p.relative_to(bundle).as_posix()
        for p in _iter_page_files(bundle)
        if p.relative_to(bundle).as_posix()[: -len(".md")] in slug_set
    ]
    return {
        "diagnostics": diagnostics,
        "orphans": orphan_slugs,
        "orphan_paths": orphan_paths,
        "errors": sum(1 for d in diagnostics if d["severity"] == "ERROR"),
        "warnings": sum(1 for d in diagnostics if d["severity"] != "ERROR"),
    }


def _index_status(bundle: Path) -> Dict[str, Any]:
    from . import graphlib, indexlib

    fts_db = indexlib.fts_index_path(bundle)
    graph_db = graphlib.graph_index_path(bundle)
    l2_db = indexlib.l2_index_path(bundle)
    return {
        "fts5": {"exists": fts_db.is_file()},
        "graph": {
            "exists": graph_db.is_file(),
            "fresh": graphlib.graph_is_fresh(bundle) if graph_db.is_file() else False,
        },
        "l2": {"exists": l2_db.is_file()},
    }


def _status_payload(state: ServeState) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "version": __version__,
        "bundle": str(state.bundle) if state.bundle else None,
        "initialized": state.initialized,
    }
    bundle = state.bundle
    if not (bundle and bundle.is_dir()):
        payload.update(
            {
                "pages": {"total": 0, "by_type": {}, "orphans": 0},
                "indexes": {
                    "fts5": {"exists": False},
                    "graph": {"exists": False, "fresh": False},
                    "l2": {"exists": False},
                },
                "lint": {"errors": 0, "warnings": 0},
                "recent_log": [],
            }
        )
        return payload

    pages = _page_summaries(bundle)
    by_type: Dict[str, int] = {}
    for page in pages:
        key = page["type"] or "(none)"
        by_type[key] = by_type.get(key, 0) + 1
    lint = _lint_payload(bundle)
    payload.update(
        {
            "pages": {
                "total": len(pages),
                "by_type": by_type,
                "orphans": sum(1 for p in pages if p["orphan"]),
            },
            "indexes": _index_status(bundle),
            "lint": {"errors": lint["errors"], "warnings": lint["warnings"]},
            "recent_log": _recent_log(bundle),
        }
    )
    return payload


def _persisted_mode(config_path: Path) -> str:
    try:
        from .config import retrieval_mode

        return retrieval_mode(config_path)
    except (ValueError, OSError):
        return "fts5"


def _search_payload(
    state: ServeState, query: str, k: int, mode: Optional[str]
) -> Dict[str, Any]:
    from . import indexlib

    bundle = state.bundle
    if not (bundle and bundle.is_dir()):
        return {"query": query, "mode": "none", "candidates": []}

    persisted = _persisted_mode(state.config_path)
    if not mode or mode == "auto":
        if indexlib.graph_index_path(bundle).is_file() and persisted != "l2":
            mode = "hybrid"
        else:
            mode = persisted
    elif mode == "fts":
        mode = "fts5"

    out: Optional[Dict[str, Any]] = None
    if mode in {"graph", "hybrid"}:
        from . import graphlib

        graph_db = graphlib.graph_index_path(bundle)
        if graph_db.is_file():
            try:
                if mode == "graph" and not graphlib.graph_is_fresh(bundle, graph_db):
                    raise ApiError(
                        409,
                        "graph index is stale; run `mneme reindex --graph` to refresh it.",
                        "stale_index",
                    )
                out = (
                    graphlib.search_graph(graph_db, query, k=k)
                    if mode == "graph"
                    else indexlib.search_hybrid(bundle, query, k=k)
                )
            except ApiError:
                raise
            except Exception as exc:  # pragma: no cover - defensive
                raise ApiError(500, f"search ({mode}) failed: {exc}", "internal")
        elif mode == "graph":
            raise ApiError(
                404,
                f"no graph index at {graph_db}; run `mneme reindex --graph` to build it.",
                "no_index",
            )
        else:
            mode = "fts5"  # hybrid without a graph falls back to FTS5

    if mode == "l2":
        db = indexlib.l2_index_path(bundle)
        if not db.is_file():
            raise ApiError(
                404,
                f"no L2 index at {db}; run `mneme reindex --l2` to build and activate it.",
                "no_index",
            )
        try:
            hits = indexlib.search_bundle(
                bundle, query, k=k, embed_fn=indexlib.default_embed_fn()
            )
        except Exception as exc:
            raise ApiError(500, f"search (L2) failed: {exc}", "internal")
        out = {
            "query": query,
            "candidates": [
                {
                    "path": h.get("path", ""),
                    "title": h.get("title", ""),
                    "snippet": h.get("text", ""),
                }
                for h in hits
            ],
        }
    elif out is None:
        db = indexlib.fts_index_path(bundle)
        if db.is_file():
            try:
                out = indexlib.search(query, db, k=k)
            except Exception as exc:
                raise ApiError(500, f"search (FTS5) failed: {exc}", "internal")
        else:
            from .cli import _cmd_search_grep

            out = _cmd_search_grep(bundle, query, k)
            mode = "l0"

    candidates = []
    for cand in out.get("candidates", []):
        path = str(cand.get("path", ""))
        if path and not path.startswith("/"):
            path = "/" + path
        candidates.append(
            {
                "path": path,
                "title": str(cand.get("title", "") or ""),
                "snippet": str(cand.get("snippet", "") or "").replace("\n", " ").strip(),
            }
        )
    return {"query": query, "mode": mode, "candidates": candidates}


def _resolve_page_path(bundle: Path, raw: str) -> Path:
    """Sandbox a bundle-relative page path inside the bundle root."""
    raw = unquote(raw or "").strip()
    if not raw or "\x00" in raw:
        raise ApiError(400, "invalid page path", "bad_request")
    rel = raw.lstrip("/")
    if not rel:
        raise ApiError(400, "invalid page path", "bad_request")
    candidate = (bundle / rel).resolve()
    try:
        candidate.relative_to(bundle)
    except ValueError:
        raise ApiError(403, f"path escapes the bundle: {raw!r}", "path_escape")
    if candidate.suffix != ".md" or not candidate.is_file():
        raise ApiError(404, f"page not found: {raw!r}", "not_found")
    return candidate


def _page_payload(state: ServeState, raw_path: str) -> Dict[str, Any]:
    bundle = state.bundle
    if not (bundle and bundle.is_dir()):
        raise ApiError(404, "bundle is not initialized", "not_found")
    from . import okflib

    target = _resolve_page_path(bundle, raw_path)
    rel = "/" + target.relative_to(bundle).as_posix()
    text = target.read_text(encoding="utf-8", errors="replace")
    parsed = okflib.parse_frontmatter(text)
    meta: Dict[str, Any] = {}
    body = text
    if parsed is not None:
        meta, body = parsed
    outlinks, inlinks = _page_links(bundle, rel)
    return {
        "path": rel,
        "frontmatter": meta,
        "body": body,
        "raw": text,
        "outlinks": outlinks,
        "inlinks": inlinks,
    }


def _dream_payload(state: ServeState) -> Dict[str, Any]:
    from . import dream as _dream
    from . import graphlib

    audit_path = state.bundle if state.bundle else Path("")
    report = _dream.dream_audit(audit_path)
    if state.bundle:
        graph_db = graphlib.graph_index_path(audit_path)
        if graph_db.is_file():
            try:
                report["graph"] = graphlib.graph_health(graph_db)
            except Exception as exc:
                report["graph"] = {"error": str(exc)}
    return report


def _graph_payload(state: ServeState) -> Dict[str, Any]:
    """Nodes/edges for the graph tab.

    P1 builds the link graph from Markdown directly (always available);
    when ``graph.db`` exists its health counters ride along as stats.
    """
    bundle = state.bundle
    if not (bundle and bundle.is_dir()):
        return {"nodes": [], "edges": [], "stats": {"nodes": 0, "edges": 0}}
    pages = _page_summaries(bundle)
    known = {p["path"] for p in pages}
    nodes = [
        {
            "id": p["path"],
            "label": p["title"] or Path(p["path"]).stem,
            "type": p["type"] or "Concept",
        }
        for p in pages
    ]
    edges: List[List[str]] = []
    for p in pages:
        try:
            text = (bundle / p["path"].lstrip("/")).read_text(
                encoding="utf-8", errors="replace"
            )
        except OSError:
            continue
        for target in dict.fromkeys(_LINK_RE.findall(text)):
            if target in known and target != p["path"]:
                edges.append([p["path"], target])
    stats: Dict[str, Any] = {"nodes": len(nodes), "edges": len(edges)}
    from . import graphlib

    graph_db = graphlib.graph_index_path(bundle)
    if graph_db.is_file():
        try:
            stats["graph_db"] = graphlib.graph_health(graph_db)
        except Exception as exc:  # pragma: no cover - defensive
            stats["graph_db"] = {"error": str(exc)}
    return {"nodes": nodes, "edges": edges, "stats": stats}


def _reindex_payload(state: ServeState) -> Dict[str, Any]:
    """Rebuild disposable caches. FTS5 always; Graph only when a graph
    index already exists (keeps L2/FTS5 mode persistence untouched and
    never installs anything). Idempotent; never touches Markdown."""
    bundle = state.bundle
    if not state.initialized:
        raise ApiError(409, "bundle is not initialized", "not_found")
    from . import graphlib, indexlib
    from .cli import _indexable_paths

    paths = _indexable_paths(bundle)
    try:
        fts_pages = indexlib.reindex_paths(paths, bundle)
    except Exception as exc:
        raise ApiError(500, f"reindex (FTS5) failed: {exc}", "internal")
    graph_result: Optional[Dict[str, Any]] = None
    if graphlib.graph_index_path(bundle).is_file():
        try:
            result = graphlib.rebuild_graph(bundle)
        except Exception as exc:
            raise ApiError(500, f"reindex (graph) failed: {exc}", "internal")
        graph_result = {
            "pages": result.indexed_pages,
            "entities": result.indexed_entities,
            "relations": result.indexed_relations,
        }
    return {
        "fts_pages": fts_pages,
        "graph": graph_result,
        "indexes": _index_status(bundle),
    }


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------


def _host_allowed(header: Optional[str], bound_host: str) -> bool:
    if not header:
        return False
    host = header.strip()
    if host.startswith("["):  # [::1]:8620
        host = host[: host.index("]") + 1] if "]" in host else host
    elif ":" in host:
        host = host.rsplit(":", 1)[0]
    allowlist = set(_HOST_ALLOWLIST)
    if bound_host not in _WILDCARD_HOSTS:
        allowlist.add(bound_host)
    return host in allowlist


def _make_handler(state: ServeState):
    class MnemeHandler(BaseHTTPRequestHandler):
        server_version = f"mneme-web/{__version__}"
        protocol_version = "HTTP/1.1"

        # -- plumbing ----------------------------------------------------

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            pass  # keep the terminal clean; startup prints the banner

        def _send_json(self, payload: Dict[str, Any], status: int = 200) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _send_error(self, err: ApiError) -> None:
            self._send_json({"error": err.message, "code": err.code}, err.status)

        def _check_host(self) -> None:
            if not _host_allowed(self.headers.get("Host"), state.host):
                raise ApiError(403, "Host header is not localhost", "forbidden_host")

        def _check_token(self) -> None:
            if self.headers.get("X-Mneme-Token") != state.token:
                raise ApiError(
                    401,
                    "missing or invalid X-Mneme-Token header",
                    "unauthorized",
                )

        # -- GET ----------------------------------------------------------

        def do_GET(self) -> None:  # noqa: N802
            try:
                self._check_host()
                parsed = urlparse(self.path)
                if parsed.path == "/":
                    self._serve_index()
                    return
                if parsed.path.startswith("/api/"):
                    self._check_token()
                    self._route_api_get(parsed.path, parse_qs(parsed.query))
                    return
                raise ApiError(404, "not found", "not_found")
            except ApiError as err:
                self._send_error(err)
            except BrokenPipeError:  # pragma: no cover - client went away
                pass
            except Exception as exc:  # pragma: no cover - defensive
                self._send_error(ApiError(500, str(exc), "internal"))

        def _serve_index(self) -> None:
            html = INDEX_HTML.replace("__MNEME_TOKEN__", state.token)
            body = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _route_api_get(self, path: str, qs: Dict[str, List[str]]) -> None:
            def one(name: str, default: Optional[str] = None) -> Optional[str]:
                values = qs.get(name)
                return values[0] if values else default

            if path == "/api/status":
                self._send_json(_status_payload(state))
            elif path == "/api/lint":
                if state.initialized:
                    self._send_json(_lint_payload(state.bundle))
                else:
                    self._send_json(
                        {
                            "diagnostics": [],
                            "orphans": [],
                            "orphan_paths": [],
                            "errors": 0,
                            "warnings": 0,
                        }
                    )
            elif path == "/api/search":
                query = (one("q") or "").strip()
                if not query:
                    raise ApiError(400, "missing query parameter `q`", "bad_request")
                try:
                    k = int(one("k", "10") or "10")
                except ValueError:
                    raise ApiError(400, "`k` must be an integer", "bad_request")
                if not 1 <= k <= 100:
                    raise ApiError(400, "`k` must be between 1 and 100", "bad_request")
                self._send_json(_search_payload(state, query, k, one("mode")))
            elif path == "/api/pages":
                pages = (
                    _page_summaries(state.bundle)
                    if state.bundle and state.bundle.is_dir()
                    else []
                )
                type_filter = one("type")
                tag_filter = one("tag")
                if type_filter:
                    pages = [p for p in pages if p["type"] == type_filter]
                if tag_filter:
                    pages = [p for p in pages if tag_filter in p["tags"]]
                self._send_json({"pages": pages})
            elif path == "/api/page":
                raw = one("path")
                if not raw:
                    raise ApiError(
                        400, "missing query parameter `path`", "bad_request"
                    )
                self._send_json(_page_payload(state, raw))
            elif path == "/api/dream":
                self._send_json(_dream_payload(state))
            elif path == "/api/graph":
                self._send_json(_graph_payload(state))
            else:
                raise ApiError(404, "not found", "not_found")

        # -- POST ---------------------------------------------------------

        def do_POST(self) -> None:  # noqa: N802
            try:
                self._check_host()
                parsed = urlparse(self.path)
                if not parsed.path.startswith("/api/"):
                    raise ApiError(404, "not found", "not_found")
                self._check_token()
                length = self.headers.get("Content-Length")
                if length is not None:
                    try:
                        size = int(length)
                    except ValueError:
                        raise ApiError(400, "bad Content-Length", "bad_request")
                    if size > MAX_BODY_BYTES:
                        # Drain a bounded amount so a client slightly over
                        # the cap finishes its send and can read the 413
                        # instead of dying on a connection reset.
                        remaining = MAX_BODY_BYTES
                        while remaining > 0:
                            chunk = self.rfile.read(min(65536, remaining))
                            if not chunk:
                                break
                            remaining -= len(chunk)
                        raise ApiError(
                            413, "request body exceeds 1 MB", "payload_too_large"
                        )
                    if size:
                        self.rfile.read(size)  # drain; P1 endpoints take no body
                if parsed.path == "/api/reindex":
                    self._send_json(_reindex_payload(state))
                    return
                raise ApiError(404, "not found", "not_found")
            except ApiError as err:
                self._send_error(err)
            except BrokenPipeError:  # pragma: no cover
                pass
            except Exception as exc:  # pragma: no cover - defensive
                self._send_error(ApiError(500, str(exc), "internal"))

    return MnemeHandler


# ---------------------------------------------------------------------------
# Server lifecycle
# ---------------------------------------------------------------------------


def make_server(
    bundle: Optional[Path],
    config_path: Path,
    host: str = "127.0.0.1",
    port: int = 8620,
) -> Tuple[ThreadingHTTPServer, ServeState]:
    """Build (but do not start) the HTTP server. ``port=0`` picks an
    ephemeral port — used by tests."""
    state = ServeState(bundle=bundle, config_path=config_path, host=host)
    handler = _make_handler(state)
    httpd = ThreadingHTTPServer((host, port), handler)
    httpd.daemon_threads = True
    return httpd, state


def serve(
    bundle: Optional[Path],
    config_path: Path,
    host: str = "127.0.0.1",
    port: int = 8620,
    open_browser: bool = False,
) -> int:
    """Run the console in the foreground until Ctrl-C."""
    httpd, state = make_server(bundle, config_path, host=host, port=port)
    bound_host, bound_port = httpd.server_address[0], httpd.server_address[1]
    url = f"http://{bound_host}:{bound_port}/"

    print("Mneme Web UI (P1 · read-only + reindex)", file=sys.stderr)
    print(f"  bundle:  {state.bundle if state.bundle else '(unresolved)'}", file=sys.stderr)
    if not state.initialized:
        print(
            "  note:    bundle has no index.md — the UI opens on the "
            "empty-bundle guide page.",
            file=sys.stderr,
        )
    print(f"  url:     {url}", file=sys.stderr)
    print(f"  token:   {state.token}", file=sys.stderr)
    print(
        "  (the page at / carries this token in memory; every /api/* call "
        "requires the X-Mneme-Token header)",
        file=sys.stderr,
    )
    if host in _WILDCARD_HOSTS:
        print("", file=sys.stderr)
        print("!" * 68, file=sys.stderr)
        print(
            "!! WARNING: binding to a non-loopback interface — the bundle is",
            file=sys.stderr,
        )
        print(
            "!! reachable by other machines on this network. Read-only +",
            file=sys.stderr,
        )
        print(
            "!! reindex only, but prefer the default --host 127.0.0.1.",
            file=sys.stderr,
        )
        print("!" * 68, file=sys.stderr)
    print("  stop:    Ctrl-C", file=sys.stderr)

    if open_browser:
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nmneme serve stopped.", file=sys.stderr)
    finally:
        httpd.server_close()
    return 0
