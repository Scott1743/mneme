"""SQLite knowledge graph derived from an OKF bundle.

The Markdown bundle remains the source of truth. ``graph.db`` is a disposable,
stdlib-only accelerator that can be deleted and rebuilt with ``mneme reindex
--graph``. Phase 1 indexes pages, tags, and Markdown links; it does not mutate
OKF pages or invoke an agent/LLM.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple

GRAPH_SCHEMA_VERSION = "1"
PAGE_ENTITY_TYPE = "page"
TAG_ENTITY_TYPE = "tag"
_LINK_RE = re.compile(r"\]\(([^)\s]+\.md)(?:#[^)]*)?\)")
_STOP_WORDS = frozenset({"what", "which", "where", "when", "with", "from", "that", "this", "and", "the", "关系", "什么", "哪些", "如何"})


@dataclass(frozen=True)
class GraphRebuildResult:
    indexed_pages: int
    indexed_entities: int
    indexed_relations: int
    db_path: Path


def graph_index_path(bundle_path: Path | str) -> Path:
    """Return the disposable graph cache path for ``bundle_path``."""
    return Path(bundle_path) / ".mneme" / "graph.db"


def open_graph(db_path: Path | str) -> sqlite3.Connection:
    """Open a graph database with foreign-key enforcement enabled."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def ensure_graph_schema(conn: sqlite3.Connection) -> None:
    """Create the v4 Phase 1 graph schema and its navigation indexes."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS entities (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT    NOT NULL,
            entity_type TEXT    NOT NULL DEFAULT 'concept',
            page_path   TEXT,
            description TEXT,
            properties  TEXT,
            created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
            updated_at  TEXT    NOT NULL DEFAULT (datetime('now')),
            UNIQUE(name, entity_type)
        );

        CREATE TABLE IF NOT EXISTS relations (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_id  INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
            predicate   TEXT    NOT NULL,
            object_id   INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
            weight      REAL    NOT NULL DEFAULT 1.0,
            source_page TEXT,
            properties  TEXT,
            created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
            UNIQUE(subject_id, predicate, object_id)
        );

        CREATE TABLE IF NOT EXISTS entity_embeddings (
            entity_id   INTEGER PRIMARY KEY REFERENCES entities(id) ON DELETE CASCADE,
            embedding   BLOB    NOT NULL,
            model       TEXT    NOT NULL,
            created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS communities (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            community_id    INTEGER NOT NULL,
            entity_id       INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
            modularity      REAL,
            label           TEXT,
            UNIQUE(community_id, entity_id)
        );

        CREATE TABLE IF NOT EXISTS meta (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_entities_name      ON entities(name);
        CREATE INDEX IF NOT EXISTS idx_entities_type      ON entities(entity_type);
        CREATE INDEX IF NOT EXISTS idx_entities_page      ON entities(page_path);
        CREATE INDEX IF NOT EXISTS idx_relations_subject  ON relations(subject_id);
        CREATE INDEX IF NOT EXISTS idx_relations_object   ON relations(object_id);
        CREATE INDEX IF NOT EXISTS idx_relations_pred     ON relations(predicate);
        CREATE INDEX IF NOT EXISTS idx_relations_pred_obj ON relations(predicate, object_id);
        CREATE INDEX IF NOT EXISTS idx_communities_entity ON communities(entity_id);
        CREATE INDEX IF NOT EXISTS idx_communities_comm   ON communities(community_id);
        """
    )
    conn.commit()


def _remove_sqlite_sidecars(path: Path) -> None:
    for suffix in ("", "-journal", "-shm", "-wal"):
        candidate = Path(f"{path}{suffix}")
        if candidate.exists():
            candidate.unlink()


def _json(value: Dict[str, Any] | None) -> str:
    return json.dumps(value or {}, ensure_ascii=False, sort_keys=True)


def _properties(value: str | None) -> Dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _write_meta(conn: sqlite3.Connection, values: Dict[str, Any]) -> None:
    conn.executemany(
        "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
        [(key, str(value)) for key, value in values.items()],
    )
    conn.commit()


def upsert_entity(
    conn: sqlite3.Connection,
    name: str,
    entity_type: str = "concept",
    *,
    page_path: str | None = None,
    description: str | None = None,
    properties: Dict[str, Any] | None = None,
) -> int:
    """Insert or update an entity and return its integer id.

    Page entities are keyed by ``page_path`` so two pages may share a title.
    Other entities use the schema's ``(name, entity_type)`` uniqueness rule.
    """
    name = str(name or "").strip()
    entity_type = str(entity_type or "concept").strip() or "concept"
    if not name:
        raise ValueError("entity name must not be empty")
    if entity_type == PAGE_ENTITY_TYPE and page_path:
        row = conn.execute(
            "SELECT id FROM entities WHERE entity_type=? AND page_path=?",
            (entity_type, page_path),
        ).fetchone()
        if row is not None:
            conn.execute(
                "UPDATE entities SET name=?, description=?, properties=?, updated_at=datetime('now') WHERE id=?",
                (name, description or "", _json(properties), row[0]),
            )
            return int(row[0])
    conn.execute(
        """
        INSERT INTO entities(name, entity_type, page_path, description, properties)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(name, entity_type) DO UPDATE SET
            page_path=COALESCE(excluded.page_path, entities.page_path),
            description=COALESCE(excluded.description, entities.description),
            properties=COALESCE(excluded.properties, entities.properties),
            updated_at=datetime('now')
        """,
        (name, entity_type, page_path, description or "", _json(properties)),
    )
    row = conn.execute(
        "SELECT id FROM entities WHERE name=? AND entity_type=?",
        (name, entity_type),
    ).fetchone()
    if row is None:  # pragma: no cover - sqlite would have raised above
        raise RuntimeError("failed to upsert graph entity")
    return int(row[0])


def upsert_relation(
    conn: sqlite3.Connection,
    subject_id: int,
    predicate: str,
    object_id: int,
    *,
    weight: float = 1.0,
    source_page: str | None = None,
    properties: Dict[str, Any] | None = None,
) -> int:
    """Insert or refresh a directed relation and return its id."""
    predicate = str(predicate or "relates_to").strip() or "relates_to"
    bounded_weight = max(0.0, min(1.0, float(weight)))
    conn.execute(
        """
        INSERT INTO relations(subject_id, predicate, object_id, weight, source_page, properties)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(subject_id, predicate, object_id) DO UPDATE SET
            weight=excluded.weight,
            source_page=excluded.source_page,
            properties=excluded.properties
        """,
        (subject_id, predicate, object_id, bounded_weight, source_page, _json(properties)),
    )
    row = conn.execute(
        "SELECT id FROM relations WHERE subject_id=? AND predicate=? AND object_id=?",
        (subject_id, predicate, object_id),
    ).fetchone()
    if row is None:  # pragma: no cover - sqlite would have raised above
        raise RuntimeError("failed to upsert graph relation")
    return int(row[0])


def _iter_page_records(bundle: Path) -> Iterable[Dict[str, Any]]:
    """Yield valid OKF page records without rejecting unrelated bad files."""
    from . import okflib

    for path in sorted(bundle.rglob("*.md")):
        if not path.is_file():
            continue
        parts = path.relative_to(bundle).parts
        if any(part == ".mneme" for part in parts):
            continue
        if any(part in {"sources", "external-sources"} for part in parts):
            continue
        if path.name in okflib.RESERVED:
            continue
        try:
            parsed = okflib.parse_frontmatter(path.read_text(encoding="utf-8"))
        except OSError:
            continue
        if parsed is None:
            continue
        meta, body = parsed
        if not str(meta.get("type", "") or "").strip():
            continue
        rel = path.relative_to(bundle).as_posix()
        tags = meta.get("tags", [])
        if isinstance(tags, str):
            tags = [tags]
        elif not isinstance(tags, list):
            tags = [str(tags)] if tags else []
        links = []
        for match in _LINK_RE.finditer(body):
            raw = match.group(1).split("?", 1)[0].split("#", 1)[0]
            if raw.startswith(("http://", "https://", "mailto:")):
                continue
            target = raw.lstrip("/")
            if target.endswith(".md"):
                links.append(target)
        yield {
            "path": rel,
            "title": str(meta.get("title", "") or rel[:-3]),
            "type": str(meta.get("type", "") or ""),
            "description": str(meta.get("description", "") or ""),
            "tags": [str(tag).strip() for tag in tags if str(tag).strip()],
            "links": sorted(set(links)),
        }


def rebuild_graph(bundle_path: Path | str, db_path: Path | str | None = None) -> GraphRebuildResult:
    """Atomically rebuild ``graph.db`` from the bundle's current Markdown."""
    root = Path(bundle_path)
    live_path = Path(db_path) if db_path is not None else graph_index_path(root)
    live_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = live_path.with_name(f"{live_path.name}.tmp")
    _remove_sqlite_sidecars(temp_path)
    records = list(_iter_page_records(root))
    conn: sqlite3.Connection | None = None
    indexed_relations = 0
    try:
        conn = open_graph(temp_path)
        ensure_graph_schema(conn)
        page_ids: Dict[str, int] = {}
        for record in records:
            page_ids[record["path"]] = upsert_entity(
                conn,
                record["path"],
                PAGE_ENTITY_TYPE,
                page_path=record["path"],
                description=record["description"],
                properties={
                    "title": record["title"],
                    "type": record["type"],
                    "missing": False,
                },
            )
        for record in records:
            subject_id = page_ids[record["path"]]
            for tag in record["tags"]:
                tag_id = upsert_entity(conn, tag, TAG_ENTITY_TYPE, description=tag)
                upsert_relation(
                    conn,
                    subject_id,
                    "tagged_by",
                    tag_id,
                    source_page=record["path"],
                )
                indexed_relations += 1
            for target in record["links"]:
                object_id = page_ids.get(target)
                if object_id is None:
                    object_id = upsert_entity(
                        conn,
                        target,
                        PAGE_ENTITY_TYPE,
                        page_path=target,
                        properties={"title": target, "missing": True},
                    )
                upsert_relation(
                    conn,
                    subject_id,
                    "relates_to",
                    object_id,
                    source_page=record["path"],
                )
                indexed_relations += 1
        conn.commit()
        _write_meta(
            conn,
            {
                "schema_version": GRAPH_SCHEMA_VERSION,
                "indexed_pages": len(records),
                "indexed_entities": conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0],
                "indexed_relations": conn.execute("SELECT COUNT(*) FROM relations").fetchone()[0],
            },
        )
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
    verify = open_graph(live_path)
    try:
        entity_count = int(verify.execute("SELECT COUNT(*) FROM entities").fetchone()[0])
        relation_count = int(verify.execute("SELECT COUNT(*) FROM relations").fetchone()[0])
    finally:
        verify.close()
    return GraphRebuildResult(len(records), entity_count, relation_count, live_path)


def _row_to_entity(row: sqlite3.Row) -> Dict[str, Any]:
    item = dict(row)
    item["properties"] = _properties(item.get("properties"))
    return item


def find_entity_by_name(conn: sqlite3.Connection, query: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Find entities using the full query and simple mention tokens."""
    terms: List[str] = []
    raw = str(query or "").strip()
    if raw:
        terms.append(raw)
        terms.extend(
            token for token in re.findall(r"[\w\u3400-\u9fff.-]+", raw)
            if token.casefold() not in _STOP_WORDS and token not in terms
        )
    seen: set[int] = set()
    found: List[Dict[str, Any]] = []
    for term in terms:
        pattern = f"%{term.casefold()}%"
        rows = conn.execute(
            """
            SELECT id, name, entity_type, page_path, description, properties
            FROM entities
            WHERE lower(name) LIKE ? OR lower(COALESCE(page_path, '')) LIKE ?
               OR lower(COALESCE(properties, '')) LIKE ?
            ORDER BY CASE WHEN lower(name)=? THEN 0 ELSE 1 END, name
            LIMIT ?
            """,
            (pattern, pattern, pattern, term.casefold(), limit),
        ).fetchall()
        for row in rows:
            if int(row[0]) in seen:
                continue
            seen.add(int(row[0]))
            found.append(_row_to_entity(row))
            if len(found) >= limit:
                return found
    return found


def bfs_neighborhood(
    conn: sqlite3.Connection,
    seed_ids: Sequence[int],
    depth: int = 2,
) -> Dict[str, Any]:
    """Traverse relations in both directions and return distances + edges."""
    depth = max(0, min(int(depth), 8))
    distances = {int(entity_id): 0 for entity_id in seed_ids}
    queue = deque(int(entity_id) for entity_id in seed_ids)
    relation_rows: Dict[int, Dict[str, Any]] = {}
    while queue:
        current = queue.popleft()
        current_depth = distances[current]
        if current_depth >= depth:
            continue
        rows = conn.execute(
            """
            SELECT id, subject_id, predicate, object_id, weight, source_page
            FROM relations WHERE subject_id=? OR object_id=?
            """,
            (current, current),
        ).fetchall()
        for row in rows:
            relation_id = int(row[0])
            relation_rows[relation_id] = dict(row)
            neighbor = int(row[3]) if int(row[1]) == current else int(row[1])
            if neighbor not in distances:
                distances[neighbor] = current_depth + 1
                queue.append(neighbor)
    return {"distances": distances, "relations": list(relation_rows.values())}


def graph_page_candidates(
    db_path: Path | str,
    query: str,
    *,
    limit: int = 50,
    depth: int = 2,
) -> List[Dict[str, Any]]:
    """Return page candidates reached from query-matched entities."""
    conn = open_graph(db_path)
    try:
        seeds = find_entity_by_name(conn, query, limit=50)
        if not seeds:
            return []
        neighborhood = bfs_neighborhood(conn, [int(item["id"]) for item in seeds], depth)
        distances = neighborhood["distances"]
        rows = conn.execute(
            "SELECT id, name, entity_type, page_path, description, properties FROM entities WHERE entity_type=?",
            (PAGE_ENTITY_TYPE,),
        ).fetchall()
        seed_names = {int(item["id"]): item["name"] for item in seeds}
        candidates = []
        for row in rows:
            entity_id = int(row[0])
            if entity_id not in distances:
                continue
            entity = _row_to_entity(row)
            if entity["properties"].get("missing"):
                continue
            entity["distance"] = distances[entity_id]
            entity["matched_entities"] = [
                name for seed_id, name in seed_names.items() if distances.get(seed_id) == 0
            ]
            candidates.append(entity)
        candidates.sort(key=lambda item: (item["distance"], item["page_path"] or item["name"]))
        return candidates[:limit]
    finally:
        conn.close()


def search_graph(db_path: Path | str, query: str, k: int = 10, depth: int = 2) -> Dict[str, Any]:
    """Return graph-only candidates in the stable CLI candidate shape."""
    candidates = graph_page_candidates(db_path, query, limit=max(k, 1), depth=depth)
    return {
        "query": query,
        "candidates": [
            {
                "path": item["page_path"] or item["name"],
                "title": item["properties"].get("title", item["name"]),
                "snippet": item.get("description", "") or "graph match",
                "graph_context": {
                    "distance": item["distance"],
                    "matched_entities": item.get("matched_entities", []),
                },
            }
            for item in candidates
        ],
    }


def graph_health(db_path: Path | str) -> Dict[str, Any]:
    """Return inexpensive graph health counters for reports and diagnostics."""
    conn = open_graph(db_path)
    try:
        entity_count = int(conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0])
        relation_count = int(conn.execute("SELECT COUNT(*) FROM relations").fetchone()[0])
        orphan_count = int(
            conn.execute(
                """
                SELECT COUNT(*) FROM entities e
                LEFT JOIN relations rs ON rs.subject_id=e.id
                LEFT JOIN relations ro ON ro.object_id=e.id
                WHERE rs.id IS NULL AND ro.id IS NULL
                """
            ).fetchone()[0]
        )
        unresolved_count = int(
            conn.execute(
                "SELECT COUNT(*) FROM entities WHERE entity_type=? AND properties LIKE '%\"missing\": true%'",
                (PAGE_ENTITY_TYPE,),
            ).fetchone()[0]
        )
        components = _connected_components(conn)
        meta = dict(conn.execute("SELECT key, value FROM meta").fetchall())
        return {
            "schema_version": meta.get("schema_version", GRAPH_SCHEMA_VERSION),
            "entity_count": entity_count,
            "relation_count": relation_count,
            "orphan_entity_count": orphan_count,
            "unresolved_page_count": unresolved_count,
            "connected_component_count": components,
        }
    finally:
        conn.close()


def _connected_components(conn: sqlite3.Connection) -> int:
    ids = {int(row[0]) for row in conn.execute("SELECT id FROM entities")}
    components = 0
    while ids:
        components += 1
        start = ids.pop()
        queue = deque([start])
        while queue:
            current = queue.popleft()
            for row in conn.execute(
                "SELECT subject_id, object_id FROM relations WHERE subject_id=? OR object_id=?",
                (current, current),
            ):
                neighbor = int(row[1]) if int(row[0]) == current else int(row[0])
                if neighbor in ids:
                    ids.remove(neighbor)
                    queue.append(neighbor)
    return components
