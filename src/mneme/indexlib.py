"""Derived L2 semantic index for an OKF bundle.

Markdown remains the source of truth. The SQLite database is a disposable,
atomically rebuilt retrieval cache backed by sqlite-vec.
"""
from __future__ import annotations

import hashlib
import os
import sqlite3
import struct
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional

EmbedFn = Callable[[List[str]], List[List[float]]]
INDEX_SCHEMA_VERSION = "1"
DEFAULT_MODEL = "BAAI/bge-small-zh-v1.5"


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
                "sqlite-vec is required for semantic indexing/search; install mneme[index]"
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
                "sqlite-vec is not loaded; install mneme[index] and rebuild the index"
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


def search(
    conn,
    query: str,
    k: int,
    embed_fn: EmbedFn | Embedder,
    concept_type: Optional[str] = None,
) -> List[Dict]:
    if not query.strip():
        raise ValueError("query must not be empty")
    if not 1 <= k <= 100:
        raise ValueError("limit must be between 1 and 100")
    embedder = _as_embedder(embed_fn)
    qvec = embedder([query])[0]
    _validate_search_index(conn, len(qvec), embedder.model_name)
    candidate_limit = min(1000, max(k, k * 5 if concept_type else k))
    try:
        rows = conn.execute(
            "SELECT chunk_id, distance FROM vec_chunks "
            "WHERE embedding MATCH ? AND k = ? ORDER BY distance",
            (_vec_blob(qvec), candidate_limit),
        ).fetchall()
    except sqlite3.Error as exc:
        raise CorruptIndexError(f"vector search failed: {exc}") from exc
    out = []
    for chunk_id, distance in rows:
        sql = "SELECT concept_id,path,title,type,text FROM chunks WHERE chunk_id=?"
        params: tuple = (chunk_id,)
        if concept_type is not None:
            sql += " AND type=?"
            params = (chunk_id, concept_type)
        row = conn.execute(sql, params).fetchone()
        if row:
            out.append(
                {
                    "concept_id": row[0],
                    "path": row[1],
                    "title": row[2],
                    "type": row[3],
                    "text": row[4],
                    "distance": float(distance),
                }
            )
            if len(out) == k:
                break
    return out


def default_embed_fn(model: str = DEFAULT_MODEL) -> Embedder:
    """Return the production fastembed provider."""
    try:
        from fastembed import TextEmbedding
    except ImportError as exc:
        raise FastEmbedUnavailableError(
            "fastembed is required for semantic indexing/search; install mneme[index]"
        ) from exc
    embedder = TextEmbedding(model_name=model)

    def fn(texts: List[str]) -> List[List[float]]:
        return [list(vector) for vector in embedder.embed(list(texts))]

    return Embedder(fn, model_name=model)


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
    live_path = Path(db_path) if db_path is not None else root / ".mneme" / "index.db"
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
    db_path = root / ".mneme" / "index.db"
    if not db_path.is_file():
        raise IndexNotFoundError(f"index not found at {db_path}; run mneme reindex")
    conn = open_index(db_path, require_vector=True)
    try:
        if read_index_meta(conn).get("indexed_concepts") == "0":
            return []
        embedder = _as_embedder(embed_fn) if embed_fn is not None else default_embed_fn()
        return search(conn, query, k, embedder, concept_type=concept_type)
    finally:
        conn.close()
