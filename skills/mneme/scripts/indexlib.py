"""L2 index: sqlite-vec + pluggable embedding (embed_fn injected).

Default embed_fn wraps fastembed; tests inject a fake. No hard dependency
on a specific embedding provider — that's the point.
"""
from __future__ import annotations

import hashlib
import struct
import sqlite3
from typing import Callable, List, Dict

EmbedFn = Callable[[List[str]], List[List[float]]]


def open_index(db_path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.enable_load_extension(True)
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        import sqlite_vec
        sqlite_vec.load(conn)
    except Exception:
        pass  # extension absent → vec ops raise at use; tested separately
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS chunks ("
        "chunk_id INTEGER PRIMARY KEY, concept_id TEXT, path TEXT, title TEXT, "
        "type TEXT, chunk_idx INTEGER, text TEXT, tags TEXT, timestamp TEXT, hash TEXT)"
    )
    conn.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")
    conn.commit()


def _ensure_vec_table(conn: sqlite3.Connection, dim: int) -> None:
    row = conn.execute("SELECT value FROM meta WHERE key='dim'").fetchone()
    if row is None:
        conn.execute(
            f"CREATE VIRTUAL TABLE IF NOT EXISTS vec_chunks USING vec0("
            f"chunk_id INTEGER PRIMARY KEY, embedding FLOAT[{dim}])"
        )
        conn.execute("INSERT INTO meta(key,value) VALUES('dim',?)", (str(dim),))
        conn.commit()
    elif int(row[0]) != dim:
        raise ValueError(f"embedding dim mismatch: index has {row[0]}, got {dim}")


def _vec_blob(vec: List[float]) -> bytes:
    return struct.pack(f"{len(vec)}f", *vec)


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
    return [p for p in parts if p]


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def upsert_concept(conn, concept_id, path, title, type, body, tags, timestamp, embed_fn: EmbedFn) -> int:
    old_ids = [r[0] for r in conn.execute("SELECT chunk_id FROM chunks WHERE concept_id=?", (concept_id,))]
    for cid in old_ids:
        conn.execute("DELETE FROM vec_chunks WHERE chunk_id=?", (cid,))
    conn.execute("DELETE FROM chunks WHERE concept_id=?", (concept_id,))
    chunks = chunk_markdown(body)
    if not chunks:
        conn.commit()
        return 0
    vectors = embed_fn(chunks)
    dim = len(vectors[0])
    _ensure_vec_table(conn, dim)
    for idx, (chunk, vec) in enumerate(zip(chunks, vectors)):
        cur = conn.execute(
            "INSERT INTO chunks(concept_id,path,title,type,chunk_idx,text,tags,timestamp,hash) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (concept_id, path, title, type, idx, chunk, tags, timestamp, _hash(chunk)),
        )
        conn.execute("INSERT INTO vec_chunks(chunk_id, embedding) VALUES (?, ?)", (cur.lastrowid, _vec_blob(vec)))
    conn.commit()
    return len(chunks)


def remove_concept(conn, concept_id) -> None:
    old_ids = [r[0] for r in conn.execute("SELECT chunk_id FROM chunks WHERE concept_id=?", (concept_id,))]
    for cid in old_ids:
        conn.execute("DELETE FROM vec_chunks WHERE chunk_id=?", (cid,))
    conn.execute("DELETE FROM chunks WHERE concept_id=?", (concept_id,))
    conn.commit()
