"""L2 index: sqlite-vec + pluggable embedding (embed_fn injected).

Default embed_fn wraps fastembed; tests inject a fake. No hard dependency
on a specific embedding provider — that's the point.
"""
from __future__ import annotations

import struct
import sqlite3
from typing import Callable, List, Dict

EmbedFn = Callable[[List[str]], List[List[float]]]


def open_index(db_path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
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
