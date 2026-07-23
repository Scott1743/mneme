"""Derived L2 semantic index for an OKF bundle.

Markdown remains the source of truth. The SQLite database is a disposable,
atomically rebuilt retrieval cache backed by sqlite-vec.
"""
from __future__ import annotations

import hashlib
import os
import re
import sqlite3
import struct
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional

EmbedFn = Callable[[List[str]], List[List[float]]]
INDEX_SCHEMA_VERSION = "1"
DEFAULT_MODEL = "BAAI/bge-small-zh-v1.5"
DEFAULT_MODEL_MAX_L2_DISTANCE = 0.90
SEMANTIC_OVERSAMPLE_FACTOR = 20
SEMANTIC_MIN_CANDIDATE_POOL = 100


def fts_index_path(bundle_path: Path | str) -> Path:
    """Return the independent zero-dependency FTS5 cache path."""
    return Path(bundle_path) / ".mneme" / "fts.db"


def graph_index_path(bundle_path: Path | str) -> Path:
    """Return the independent v4 graph cache path."""
    from .graphlib import graph_index_path as _graph_index_path

    return _graph_index_path(bundle_path)


def l2_index_path(bundle_path: Path | str) -> Path:
    """Return the independent optional semantic cache path."""
    return Path(bundle_path) / ".mneme" / "l2.db"


class IndexErrorBase(RuntimeError):
    """Base class for L2 operational errors; the OKF bundle may still be valid."""


class IndexNotFoundError(IndexErrorBase):
    pass


class SqliteVecUnavailableError(IndexErrorBase):
    pass


class FastEmbedUnavailableError(IndexErrorBase):
    pass


class IncompatibleIndexError(IndexErrorBase):
    pass


class CorruptIndexError(IndexErrorBase):
    pass


@dataclass(frozen=True)
class Embedder:
    fn: EmbedFn
    model_name: str = "custom"

    def __call__(self, texts: List[str]) -> List[List[float]]:
        return self.fn(texts)


@dataclass(frozen=True)
class ReindexResult:
    indexed_concepts: int
    indexed_chunks: int
    skipped_concepts: int
    db_path: Path


def _as_embedder(embed_fn: EmbedFn | Embedder) -> Embedder:
    if isinstance(embed_fn, Embedder):
        return embed_fn
    return Embedder(embed_fn)


def _load_sqlite_vec(conn: sqlite3.Connection, required: bool) -> None:
    try:
        import sqlite_vec
    except ImportError as exc:
        if required:
            raise SqliteVecUnavailableError(
                "sqlite-vec is required for semantic indexing/search. "
                "Install once with: pip install 'sqlite-vec>=0.1.9,<0.2'"
            ) from exc
        return
    try:
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
    except Exception as exc:
        raise SqliteVecUnavailableError(f"failed to load sqlite-vec: {exc}") from exc


def open_index(db_path, *, require_vector: bool = False) -> sqlite3.Connection:
    try:
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA foreign_keys=ON")
        _load_sqlite_vec(conn, require_vector)
        return conn
    except Exception:
        if "conn" in locals():
            conn.close()
        raise


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Create the v2.0 L1 schema (pages + pages_fts with `body`) and the
    legacy v1.x L2 schema (chunks + meta) for backward compatibility.

    The L1 schema is the new zero-dep FTS5-backed full-text index that
    `reindex_paths` populates. The L2 schema is left in place so the
    v1.x reindex_bundle / search_bundle paths keep working until the
    later tasks remove them outright.
    """
    # v2.0 L1 — zero-dep FTS5 with a populated `body` column.
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS pages (
            id INTEGER PRIMARY KEY,
            path TEXT UNIQUE NOT NULL,
            type TEXT,
            title TEXT,
            description TEXT,
            tags TEXT,
            mtime REAL,
            body TEXT
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS pages_fts USING fts5(
            title, description, tags, body,
            content='pages', content_rowid='id'
        );
        CREATE TRIGGER IF NOT EXISTS pages_ai AFTER INSERT ON pages BEGIN
            INSERT INTO pages_fts(rowid, title, description, tags, body)
            VALUES (new.id, new.title, new.description, new.tags, new.body);
        END;
        CREATE TRIGGER IF NOT EXISTS pages_ad AFTER DELETE ON pages BEGIN
            INSERT INTO pages_fts(pages_fts, rowid, title, description, tags, body)
            VALUES('delete', old.id, old.title, old.description, old.tags, old.body);
        END;
        CREATE TRIGGER IF NOT EXISTS pages_au AFTER UPDATE ON pages BEGIN
            INSERT INTO pages_fts(pages_fts, rowid, title, description, tags, body)
            VALUES('delete', old.id, old.title, old.description, old.tags, old.body);
            INSERT INTO pages_fts(rowid, title, description, tags, body)
            VALUES (new.id, new.title, new.description, new.tags, new.body);
        END;
        """
    )
    # v1.x L2 legacy — chunks + meta (preserved for reindex_bundle).
    conn.execute(
        "CREATE TABLE IF NOT EXISTS chunks ("
        "chunk_id INTEGER PRIMARY KEY, concept_id TEXT, path TEXT, title TEXT, "
        "type TEXT, chunk_idx INTEGER, text TEXT, tags TEXT, timestamp TEXT, hash TEXT)"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_concept ON chunks(concept_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_type ON chunks(type)")
    conn.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")
    conn.commit()


def _write_meta(conn: sqlite3.Connection, values: Dict[str, str]) -> None:
    conn.executemany(
        "INSERT OR REPLACE INTO meta(key,value) VALUES(?,?)",
        [(key, str(value)) for key, value in values.items()],
    )
    conn.commit()


def read_index_meta(conn: sqlite3.Connection) -> Dict[str, str]:
    try:
        return dict(conn.execute("SELECT key,value FROM meta").fetchall())
    except sqlite3.Error as exc:
        raise CorruptIndexError(f"cannot read index metadata: {exc}") from exc


def _ensure_vec_table(conn: sqlite3.Connection, dim: int) -> None:
    row = conn.execute("SELECT value FROM meta WHERE key='dim'").fetchone()
    if row is None:
        try:
            conn.execute(
                f"CREATE VIRTUAL TABLE IF NOT EXISTS vec_chunks USING vec0("
                f"chunk_id INTEGER PRIMARY KEY, embedding FLOAT[{dim}])"
            )
        except sqlite3.Error as exc:
            raise SqliteVecUnavailableError(
                "sqlite-vec is not loaded; install via "
                "`pip install 'sqlite-vec>=0.1.9,<0.2' fastembed` and rebuild the index"
            ) from exc
        _write_meta(conn, {"dim": str(dim)})
    elif int(row[0]) != dim:
        raise IncompatibleIndexError(
            f"embedding dimension mismatch: index has {row[0]}, query uses {dim}; run mneme reindex"
        )


def _validate_search_index(conn: sqlite3.Connection, dim: int, model_name: str) -> None:
    meta = read_index_meta(conn)
    if not meta:
        raise CorruptIndexError("index metadata is missing; run mneme reindex")
    if meta.get("schema_version") != INDEX_SCHEMA_VERSION:
        raise IncompatibleIndexError("index schema is incompatible; run mneme reindex")
    stored_dim = meta.get("dim")
    if stored_dim is None or int(stored_dim) != dim:
        raise IncompatibleIndexError(
            f"embedding dimension mismatch: index has {stored_dim}, query uses {dim}; run mneme reindex"
        )
    stored_model = meta.get("embedding_model", "custom")
    if model_name != "custom" and stored_model not in ("custom", model_name):
        raise IncompatibleIndexError(
            f"embedding model mismatch: index uses {stored_model}, query uses {model_name}; run mneme reindex"
        )
    table = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE name='vec_chunks' AND type='table'"
    ).fetchone()
    if table is None:
        raise CorruptIndexError("vector table is missing; run mneme reindex")


def chunk_markdown(text: str) -> List[str]:
    parts, cur = [], []
    for line in text.splitlines():
        if line.startswith("#") and cur:
            parts.append("\n".join(cur).strip())
            cur = [line]
        else:
            cur.append(line)
    if cur:
        parts.append("\n".join(cur).strip())
    return [part for part in parts if part]


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _vec_blob(vec: List[float]) -> bytes:
    return struct.pack(f"{len(vec)}f", *vec)


def upsert_concept(
    conn,
    concept_id,
    path,
    title,
    type,
    body,
    tags,
    timestamp,
    embed_fn: EmbedFn | Embedder,
) -> int:
    old_ids = [
        row[0]
        for row in conn.execute("SELECT chunk_id FROM chunks WHERE concept_id=?", (concept_id,))
    ]
    for chunk_id in old_ids:
        conn.execute("DELETE FROM vec_chunks WHERE chunk_id=?", (chunk_id,))
    conn.execute("DELETE FROM chunks WHERE concept_id=?", (concept_id,))
    chunks = chunk_markdown(body)
    if not chunks:
        conn.commit()
        return 0
    vectors = _as_embedder(embed_fn)(chunks)
    if len(vectors) != len(chunks) or not vectors or not vectors[0]:
        raise ValueError("embedder returned an invalid vector batch")
    dim = len(vectors[0])
    if any(len(vector) != dim for vector in vectors):
        raise ValueError("embedder returned vectors with inconsistent dimensions")
    _ensure_vec_table(conn, dim)
    _write_meta(
        conn,
        {"schema_version": INDEX_SCHEMA_VERSION, "embedding_model": _as_embedder(embed_fn).model_name},
    )
    for idx, (chunk, vector) in enumerate(zip(chunks, vectors)):
        cur = conn.execute(
            "INSERT INTO chunks(concept_id,path,title,type,chunk_idx,text,tags,timestamp,hash) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (concept_id, path, title, type, idx, chunk, tags, timestamp, _hash(chunk)),
        )
        conn.execute(
            "INSERT INTO vec_chunks(chunk_id, embedding) VALUES (?, ?)",
            (cur.lastrowid, _vec_blob(vector)),
        )
    conn.commit()
    return len(chunks)


def remove_concept(conn, concept_id) -> None:
    old_ids = [
        row[0]
        for row in conn.execute("SELECT chunk_id FROM chunks WHERE concept_id=?", (concept_id,))
    ]
    for chunk_id in old_ids:
        conn.execute("DELETE FROM vec_chunks WHERE chunk_id=?", (chunk_id,))
    conn.execute("DELETE FROM chunks WHERE concept_id=?", (concept_id,))
    conn.commit()


def search_semantic(
    conn,
    query: str,
    k: int,
    embed_fn: EmbedFn | Embedder,
    concept_type: Optional[str] = None,
    max_distance: Optional[float] = None,
) -> List[Dict]:
    """L2 vector-search backend (sqlite-vec + fastembed).

    Deferred from the v2.0 user-facing ``search`` surface — the L2
    stack is not part of v2.0 (deferred to v2.1 per
    ``docs/superpowers/plans/2026-07-13-mneme-2.0-implementation.md``).
    This function is retained so ``reindex_bundle`` /
    ``search_bundle`` keep working for the existing tests that
    exercise the L2 path (``tests/test_blackbox_news.py`` and
    ``tests/test_indexlib.py``).

    Use the new top-level :func:`search` for v2.0 candidate search;
    it does not require L2 deps.
    """
    if not query.strip():
        raise ValueError("query must not be empty")
    if not 1 <= k <= 100:
        raise ValueError("limit must be between 1 and 100")
    if max_distance is not None and max_distance < 0:
        raise ValueError("max_distance must be non-negative")
    embedder = _as_embedder(embed_fn)
    qvec = embedder([query])[0]
    _validate_search_index(conn, len(qvec), embedder.model_name)
    # sqlite-vec ranks chunks, while Mneme's public search contract returns
    # pages. Pull a wider chunk pool so one long page cannot consume top-k.
    candidate_limit = min(
        1000,
        max(SEMANTIC_MIN_CANDIDATE_POOL, k * SEMANTIC_OVERSAMPLE_FACTOR),
    )
    try:
        rows = conn.execute(
            "SELECT chunk_id, distance FROM vec_chunks "
            "WHERE embedding MATCH ? AND k = ? ORDER BY distance",
            (_vec_blob(qvec), candidate_limit),
        ).fetchall()
    except sqlite3.Error as exc:
        raise CorruptIndexError(f"vector search failed: {exc}") from exc
    out = []
    seen_concepts = set()
    for chunk_id, distance in rows:
        distance = float(distance)
        if max_distance is not None and distance > max_distance:
            # Rows are ordered by distance, so every remaining row is also
            # outside the relevance gate.
            break
        sql = "SELECT concept_id,path,title,type,text FROM chunks WHERE chunk_id=?"
        params: tuple = (chunk_id,)
        if concept_type is not None:
            sql += " AND type=?"
            params = (chunk_id, concept_type)
        row = conn.execute(sql, params).fetchone()
        if row and row[0] not in seen_concepts:
            seen_concepts.add(row[0])
            out.append(
                {
                    "concept_id": row[0],
                    "path": row[1],
                    "title": row[2],
                    "type": row[3],
                    "text": row[4],
                    "distance": distance,
                }
            )
            if len(out) == k:
                break
    return out


def _semantic_max_distance(meta: Dict[str, str]) -> Optional[float]:
    """Return a calibrated relevance gate for known normalized embeddings.

    FastEmbed normalizes BGE-small-zh-v1.5 vectors and sqlite-vec's schema uses
    Euclidean distance. A 0.90 cutoff corresponds to cosine similarity around
    0.595. Custom embedders keep raw top-k behavior because their scale is not
    known and must not inherit a model-specific threshold.
    """
    if meta.get("embedding_model") == DEFAULT_MODEL:
        return DEFAULT_MODEL_MAX_L2_DISTANCE
    return None


def default_embed_fn(model: str = DEFAULT_MODEL) -> Embedder:
    """Return the production fastembed provider.

    The model cache is pinned to a stable location under the user's
    home directory (``~/.cache/mneme/models/`` on POSIX,
    ``~/Library/Caches/mneme/models/`` on macOS) so a reboot or temp
    cleanup does not trigger a re-download of the ~91MB BGE model.
    The readiness assessment flagged the previous behavior — letting
    fastembed default to an OS temporary cache — as avoidable L2
    overhead.
    """
    try:
        from fastembed import TextEmbedding
    except ImportError as exc:
        raise FastEmbedUnavailableError(
            "fastembed is required for semantic indexing/search. "
            "Install once with: pip install 'fastembed>=0.8.0,<0.9'"
        ) from exc
    cache_dir = _model_cache_dir()
    cache_dir.mkdir(parents=True, exist_ok=True)
    embedder = TextEmbedding(model_name=model, cache_dir=str(cache_dir))

    def fn(texts: List[str]) -> List[List[float]]:
        return [list(vector) for vector in embedder.embed(list(texts))]

    return Embedder(fn, model_name=model)


def _model_cache_dir() -> Path:
    """Return the stable on-disk cache directory for fastembed models.

    Uses ``~/.cache/mneme/models/`` on POSIX and
    ``~/Library/Caches/mneme/models/`` on macOS so the cache survives
    OS temp cleanup. Honors ``MNEME_MODEL_CACHE`` for users who want
    to relocate it (e.g. a shared NAS or a tmpfs for tests).
    """
    override = os.environ.get("MNEME_MODEL_CACHE")
    if override:
        return Path(override).expanduser()
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "mneme" / "models"
    return Path.home() / ".cache" / "mneme" / "models"


def iter_indexable_concepts(bundle_path) -> Iterable[str]:
    from . import okflib

    for concept_id in okflib.list_concepts(bundle_path):
        if concept_id == "archive" or concept_id.startswith("archive/"):
            continue
        yield concept_id


def _root_okf_version(root: Path) -> str:
    from . import okflib

    index = root / "index.md"
    if not index.exists():
        return ""
    parsed = okflib.parse_frontmatter(index.read_text(encoding="utf-8"))
    return str(parsed[0].get("okf_version", "")) if parsed else ""


def _remove_sqlite_sidecars(path: Path) -> None:
    for suffix in ("", "-journal", "-shm", "-wal"):
        candidate = Path(f"{path}{suffix}")
        if candidate.exists():
            candidate.unlink()


def reindex_bundle(
    bundle_path,
    embed_fn: EmbedFn | Embedder,
    db_path=None,
) -> ReindexResult:
    from . import okflib

    root = Path(bundle_path)
    live_path = Path(db_path) if db_path is not None else l2_index_path(root)
    live_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = live_path.with_name(f"{live_path.name}.tmp")
    _remove_sqlite_sidecars(temp_path)
    embedder = _as_embedder(embed_fn)
    indexed_concepts = 0
    indexed_chunks = 0
    skipped_concepts = 0
    conn = None
    try:
        conn = open_index(temp_path, require_vector=True)
        ensure_schema(conn)
        for concept_id in iter_indexable_concepts(root):
            parsed = okflib.read_concept(root, concept_id)
            if not parsed:
                skipped_concepts += 1
                continue
            meta, body = parsed
            chunks = upsert_concept(
                conn,
                concept_id,
                f"{concept_id}.md",
                meta.get("title", concept_id),
                meta.get("type", ""),
                body,
                str(meta.get("tags", [])),
                meta.get("timestamp", ""),
                embedder,
            )
            indexed_concepts += 1
            indexed_chunks += chunks
        _write_meta(
            conn,
            {
                "schema_version": INDEX_SCHEMA_VERSION,
                "embedding_model": embedder.model_name,
                "okf_version": _root_okf_version(root),
                "indexed_concepts": str(indexed_concepts),
                "indexed_chunks": str(indexed_chunks),
                "last_sync": datetime.now(timezone.utc).isoformat(),
            },
        )
        conn.commit()
        conn.close()
        conn = None
        with temp_path.open("rb") as handle:
            os.fsync(handle.fileno())
        temp_path.replace(live_path)
    except Exception:
        if conn is not None:
            conn.close()
        _remove_sqlite_sidecars(temp_path)
        raise
    return ReindexResult(indexed_concepts, indexed_chunks, skipped_concepts, live_path)


def search_bundle(
    bundle_path,
    query: str,
    k: int = 10,
    concept_type: Optional[str] = None,
    embed_fn: EmbedFn | Embedder | None = None,
) -> List[Dict]:
    root = Path(bundle_path)
    db_path = l2_index_path(root)
    if not db_path.is_file():
        raise IndexNotFoundError(f"index not found at {db_path}; run mneme reindex")
    conn = open_index(db_path, require_vector=True)
    try:
        meta = read_index_meta(conn)
        if meta.get("indexed_concepts") == "0":
            return []
        embedder = _as_embedder(embed_fn) if embed_fn is not None else default_embed_fn()
        return search_semantic(
            conn,
            query,
            k,
            embedder,
            concept_type=concept_type,
            max_distance=_semantic_max_distance(meta),
        )
    finally:
        conn.close()


def reindex_paths(paths, bundle) -> int:
    """Atomic snapshot rebuild of the v2.0 L1 (FTS5) index for `paths`.

    Writes the new index into ``<bundle>/.mneme/fts.db.tmp``, fsyncs
    it, then ``os.replace``s it into the live ``fts.db`` path. A
    crash mid-build never leaves the live db torn — the temp file is
    unlinked on any error and the previous live db (if any) stays in
    place untouched.

    Each input path is parsed with :func:`mneme.okflib.parse_frontmatter`
    so the frontmatter dict and body come from a single, well-tested
    source. Pages with no parseable frontmatter are skipped (OKF §9:
    one bad file must not invalidate the rest).

    Pure stdlib + sqlite3 + FTS5. v2.0 has no L2 — this function does
    not import ``sqlite_vec`` or ``fastembed``.

    Returns the number of pages actually written to the index.
    """
    from . import okflib

    root = Path(bundle)
    live_path = fts_index_path(root)
    live_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = live_path.with_name(f"{live_path.name}.tmp")
    _remove_sqlite_sidecars(temp_path)
    indexed = 0
    conn = None
    try:
        conn = sqlite3.connect(str(temp_path))
        ensure_schema(conn)
        for path in paths:
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            parsed = okflib.parse_frontmatter(text)
            if parsed is None:
                # No frontmatter block — OKF §9 tolerance, skip silently.
                continue
            meta, body = parsed
            try:
                rel = path.relative_to(root).as_posix()
            except ValueError:
                # Path outside bundle — skip; OKF §9 one-bad-file isolation.
                continue
            tags = meta.get("tags", [])
            # okflib's lenient parser returns tags as a list when written
            # like `tags: [a, b]`; the column is a string for portability.
            if isinstance(tags, list):
                tags_str = ",".join(str(t) for t in tags)
            else:
                tags_str = str(tags) if tags is not None else ""
            try:
                mtime = path.stat().st_mtime
            except OSError:
                mtime = 0.0
            conn.execute(
                "INSERT OR REPLACE INTO pages("
                "path, type, title, description, tags, mtime, body"
                ") VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    rel,
                    str(meta.get("type", "") or ""),
                    str(meta.get("title", "") or ""),
                    str(meta.get("description", "") or ""),
                    tags_str,
                    mtime,
                    body,
                ),
            )
            indexed += 1
        conn.commit()
        conn.close()
        conn = None
        with temp_path.open("rb") as handle:
            os.fsync(handle.fileno())
        os.replace(temp_path, live_path)
    except Exception:
        if conn is not None:
            conn.close()
        _remove_sqlite_sidecars(temp_path)
        raise
    return indexed


def search_paths(query: str, db: Path, paths: Iterable[str], k: int = 10) -> Dict:
    """Search FTS5 while restricting candidates to bundle-relative paths."""
    if not query.strip():
        raise ValueError("query must not be empty")
    if not 1 <= k <= 100:
        raise ValueError("limit must be between 1 and 100")
    selected = list(dict.fromkeys(str(path) for path in paths if str(path)))
    if not selected:
        return {"query": query, "candidates": []}
    placeholders = ", ".join("?" for _ in selected)
    conn = sqlite3.connect(str(db))
    try:
        rows = conn.execute(
            "SELECT p.path, p.title, "
            "snippet(pages_fts, 3, '|', '|', '…', 8) "
            "FROM pages_fts JOIN pages p ON p.id = pages_fts.rowid "
            f"WHERE pages_fts MATCH ? AND p.path IN ({placeholders}) "
            "ORDER BY rank LIMIT ?",
            (query, *selected, k),
        ).fetchall()
    finally:
        conn.close()
    return {
        "query": query,
        "candidates": [
            {"path": row[0], "title": row[1] or "", "snippet": row[2] or ""}
            for row in rows
        ],
    }


def search_hybrid(
    bundle_path: Path | str,
    query: str,
    k: int = 10,
    *,
    alpha: float = 0.75,
    beta: float = 0.10,
    gamma: float = 0.15,
    depth: int = 2,
    include_l2: bool = False,
    embed_fn: EmbedFn | Embedder | None = None,
) -> Dict:
    """Fuse page-level Graph, FTS5, and optional L2 candidate ranking.

    L2 remains explicitly opt-in. Callers enable its leg only when the
    persisted retrieval mode is ``l2``; an unavailable active L2 raises rather
    than silently degrading. Each leg is reduced to one score per page before
    fusion, and weights are renormalized across legs that returned candidates.
    """
    from . import graphlib

    if not query.strip():
        raise ValueError("query must not be empty")
    if not 1 <= k <= 100:
        raise ValueError("limit must be between 1 and 100")
    root = Path(bundle_path)
    graph_db = graphlib.graph_index_path(root)
    fts_db = fts_index_path(root)
    l2_db = l2_index_path(root)
    if include_l2 and not l2_db.is_file():
        raise IndexNotFoundError(
            f"no L2 index at {l2_db}; run `mneme reindex --l2` to build and activate it."
        )

    graph_available = graph_db.is_file()
    graph_fresh = graph_available and graphlib.graph_is_fresh(root, graph_db)
    graph_candidates = (
        graphlib.graph_page_candidates(graph_db, query, limit=max(k * 10, 50), depth=depth)
        if graph_fresh else []
    )

    pool_size = min(max(k * 10, 50), 100)
    # FTS5 searches globally. Graph is an additional signal, never a hard
    # candidate filter, so sparse graph coverage cannot hide lexical hits.
    fts_candidates = (
        search(query, fts_db, k=pool_size)["candidates"] if fts_db.is_file() else []
    )
    l2_hits = (
        search_bundle(root, query, k=pool_size, embed_fn=embed_fn) if include_l2 else []
    )

    by_path: Dict[str, Dict] = {}
    for item in graph_candidates:
        path = str(item.get("page_path") or item.get("name") or "")
        if not path:
            continue
        props = item.get("properties", {})
        by_path[path] = {
            "path": path,
            "title": props.get("title", item.get("name", path)),
            "snippet": item.get("description", "") or "graph match",
            "distance": int(item.get("distance", 0)),
            "graph_score": float(item.get("graph_score", 0.0)),
            "matched_entities": item.get("matched_entities", []),
        }

    for candidate in fts_candidates:
        by_path.setdefault(
            candidate["path"],
            {
                "path": candidate["path"],
                "title": candidate["title"],
                "snippet": candidate["snippet"],
                "distance": None,
                "graph_score": 0.0,
                "matched_entities": [],
            },
        )

    for hit in l2_hits:
        path = str(hit.get("path", ""))
        if not path:
            continue
        by_path.setdefault(
            path,
            {
                "path": path,
                "title": str(hit.get("title", "")),
                "snippet": str(hit.get("text", "")),
                "distance": None,
                "graph_score": 0.0,
                "matched_entities": [],
            },
        )

    graph_by_path = {
        str(item.get("page_path") or item.get("name") or ""): item
        for item in graph_candidates
        if str(item.get("page_path") or item.get("name") or "")
    }
    fts_by_path = {item["path"]: item for item in fts_candidates}
    l2_by_path = {
        str(item.get("path", "")): item for item in l2_hits if str(item.get("path", ""))
    }
    fts_rank = {item["path"]: rank for rank, item in enumerate(fts_candidates)}
    l2_rank = {
        str(item.get("path", "")): rank
        for rank, item in enumerate(l2_hits)
        if str(item.get("path", ""))
    }

    active_weights = {
        "graph": max(0.0, alpha) if graph_by_path else 0.0,
        "fts5": max(0.0, beta) if fts_by_path else 0.0,
        "l2": max(0.0, gamma) if l2_by_path else 0.0,
    }
    total_weight = sum(active_weights.values())
    active_legs = [name for name, weight in active_weights.items() if weight > 0]
    if by_path and total_weight <= 0:
        available = [
            name
            for name, candidates in (
                ("graph", graph_by_path),
                ("fts5", fts_by_path),
                ("l2", l2_by_path),
            )
            if candidates
        ]
        active_weights = {name: (1.0 if name in available else 0.0) for name in active_weights}
        active_legs = available
        total_weight = float(len(available))
    normalized_weights = {
        name: round(weight / total_weight, 6) if total_weight else 0.0
        for name, weight in active_weights.items()
    }

    merged = []
    for path, item in by_path.items():
        graph_score = item["graph_score"] if item["distance"] is not None else 0.0
        fts_score = 1.0 / (1.0 + fts_rank[path]) if path in fts_rank else 0.0
        l2_score = 1.0 / (1.0 + l2_rank[path]) if path in l2_rank else 0.0
        final_score = (
            (
                active_weights["graph"] * graph_score
                + active_weights["fts5"] * fts_score
                + active_weights["l2"] * l2_score
            )
            / total_weight
            if total_weight
            else 0.0
        )
        display_item = fts_by_path.get(path) or l2_by_path.get(path) or item
        l2_item = l2_by_path.get(path)
        candidate = {
            "path": path,
            "title": display_item.get("title", ""),
            "snippet": display_item.get("snippet", display_item.get("text", "")),
            "score": round(final_score, 6),
            "graph_score": round(graph_score, 6),
            "fts_score": round(fts_score, 6),
            "l2_score": round(l2_score, 6),
            "graph_context": {
                "distance": item["distance"],
                "matched_entities": item["matched_entities"],
            },
        }
        if l2_item is not None and l2_item.get("distance") is not None:
            candidate["distance"] = float(l2_item["distance"])
        merged.append(candidate)
    merged.sort(key=lambda candidate: (-candidate["score"], candidate["path"]))

    reason = None
    if not graph_available:
        reason = "graph index missing"
    elif not graph_fresh:
        reason = "graph index is stale"
    elif not graph_candidates:
        reason = "no graph entity match"
    fallback = None
    if active_legs == ["fts5"]:
        fallback = "fts5"
    elif (
        not active_legs
        and not include_l2
        and not graph_available
        and not fts_db.is_file()
    ):
        fallback = "l0"

    queried_sources = []
    if graph_fresh:
        queried_sources.append("graph")
    if fts_db.is_file():
        queried_sources.append("fts5")
    if include_l2:
        queried_sources.append("l2")

    context = {
        "mode": "hybrid",
        "depth": depth,
        "graph_candidates": len(graph_by_path),
        "fts_candidates": len(fts_by_path),
        "l2_candidates": len(l2_by_path),
        "graph_fresh": graph_fresh,
        "weights": normalized_weights,
        "active_sources": active_legs,
        "queried_sources": queried_sources,
        "embedding_weight": gamma,
        "embedding_enabled": include_l2,
        "l2_weight": gamma,
        "l2_enabled": include_l2,
    }
    if reason:
        context["reason"] = reason
    if fallback:
        context["fallback"] = fallback
    return {
        "query": query,
        "candidates": merged[:k],
        "graph_context": context,
    }


def search(query: str, db: Path, k: int = 10) -> Dict:
    """v2.0 FTS5 candidate search — no L2 deps.

    Returns a dict of the form::

        {
            "query": <query>,
            "candidates": [
                {"path": ..., "title": ..., "snippet": ...}, ...
            ],
        }

    Each candidate is a *navigation hint*, not a final answer. The
    host agent (Claude Code) is expected to ``Read`` each candidate
    page in full before composing a response. This separation —
    "the CLI produces candidates, the agent produces the answer" —
    is the v2.0 contract; see ``docs/superpowers/plans/2026-07-13-
    mneme-2.0-implementation.md`` Task 4.

    Implementation notes:

    - Uses the v1.x FTS5 column-indexing convention for the
      ``pages_fts`` virtual table declared in :func:`ensure_schema`:
      ``title=0, description=1, tags=2, body=3``. Task 3 corrected
      the original plan (which had body at column 4); this function
      pins column 3 to surface body-only matches in the snippet.
    - Snippet delimiters are ``|...|…`` (start/sep/end) with up to
      8 tokens of context — a deliberately compact snippet so the
      host agent still does the work of reading the full page.
    - Pure stdlib + sqlite3 + FTS5. Does NOT import ``sqlite_vec``
      or ``fastembed``. L2 lives at :func:`search_semantic` and is
      deferred to v2.1.
    """
    if not query.strip():
        raise ValueError("query must not be empty")
    if not 1 <= k <= 100:
        raise ValueError("limit must be between 1 and 100")
    db_path = Path(db)
    conn = sqlite3.connect(str(db_path))
    match_query = query
    try:
        statement = (
            "SELECT p.path, p.title, "
            "snippet(pages_fts, 3, '|', '|', '…', 8) "
            "FROM pages_fts JOIN pages p ON p.id = pages_fts.rowid "
            "WHERE pages_fts MATCH ? ORDER BY rank LIMIT ?"
        )
        try:
            rows = conn.execute(statement, (match_query, k)).fetchall()
        except sqlite3.OperationalError as exc:
            # Natural-language punctuation such as '-' can be interpreted as
            # an FTS5 operator or column name. Retry as quoted tokens.
            message = str(exc).lower()
            if "fts5" not in message and "no such column" not in message:
                raise
            tokens = [token for token in re.findall(r"[^\s]+", query) if token]
            match_query = " AND ".join(
                f'"{token.replace(chr(34), chr(34) * 2)}"' for token in tokens
            )
            rows = conn.execute(statement, (match_query, k)).fetchall()
    finally:
        conn.close()
    return {
        "query": query,
        "candidates": [
            {"path": row[0], "title": row[1] or "", "snippet": row[2] or ""}
            for row in rows
        ],
    }
