"""Disposable SQLite FTS5 index for an OKF bundle.

Markdown pages remain the source of truth. This module deliberately uses
only the Python standard library: v2.0 has no semantic/vector search path.
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any, Iterable


class IndexNotFoundError(RuntimeError):
    """Raised when a requested derived FTS5 index does not exist."""


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Create the FTS5 tables and synchronization triggers."""
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


def _remove_sidecars(path: Path) -> None:
    for suffix in ("", "-journal", "-shm", "-wal"):
        candidate = Path(f"{path}{suffix}")
        if candidate.exists():
            candidate.unlink()


def reindex_paths(paths: Iterable[Path], bundle: Path) -> int:
    """Atomically rebuild the derived FTS5 index from valid wiki pages."""
    from . import okflib

    root = Path(bundle)
    live_path = root / ".mneme" / "index.db"
    live_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = live_path.with_name(f"{live_path.name}.tmp")
    _remove_sidecars(temp_path)
    indexed = 0
    conn: sqlite3.Connection | None = None
    try:
        conn = sqlite3.connect(str(temp_path))
        ensure_schema(conn)
        for path in paths:
            try:
                text = path.read_text(encoding="utf-8")
                rel = path.relative_to(root).as_posix()
            except (OSError, ValueError):
                continue
            parsed = okflib.parse_frontmatter(text)
            if parsed is None:
                continue
            meta, body = parsed
            tags = meta.get("tags", [])
            tags_text = ",".join(str(tag) for tag in tags) if isinstance(tags, list) else str(tags or "")
            try:
                mtime = path.stat().st_mtime
            except OSError:
                mtime = 0.0
            conn.execute(
                "INSERT OR REPLACE INTO pages(path, type, title, description, tags, mtime, body) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    rel,
                    str(meta.get("type", "") or ""),
                    str(meta.get("title", "") or ""),
                    str(meta.get("description", "") or ""),
                    tags_text,
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
        _remove_sidecars(temp_path)
        raise
    return indexed


def search(query: str, db: Path, k: int = 10) -> dict[str, Any]:
    """Return FTS5 candidate paths, titles, and compact body snippets."""
    if not query.strip():
        raise ValueError("query must not be empty")
    if not 1 <= k <= 100:
        raise ValueError("limit must be between 1 and 100")
    db_path = Path(db)
    if not db_path.is_file():
        raise IndexNotFoundError(f"index not found at {db_path}; run mneme reindex")
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute(
            "SELECT p.path, p.title, snippet(pages_fts, 3, '|', '|', '...', 8) "
            "FROM pages_fts JOIN pages p ON p.id = pages_fts.rowid "
            "WHERE pages_fts MATCH ? ORDER BY rank LIMIT ?",
            (query, k),
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
