"""SQLite knowledge graph derived from an OKF bundle.

The Markdown bundle remains the source of truth. ``graph.db`` is a disposable,
stdlib-only accelerator that can be deleted and rebuilt with ``mneme reindex
--graph``. Phase 1 indexes pages, tags, and Markdown links; it does not mutate
OKF pages or invoke an agent/LLM.
"""
from __future__ import annotations

import json
import hashlib
import os
import re
import sqlite3
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple

GRAPH_SCHEMA_VERSION = "3"
PAGE_ENTITY_TYPE = "page"
TAG_ENTITY_TYPE = "tag"
ENTITY_SOURCE_PAGE = "page"
ENTITY_SOURCE_TAG = "tag"
ENTITY_SOURCE_LLM = "llm_extracted"
REL_SOURCE_TAG = "tag"
REL_SOURCE_LINK = "link"
REL_SOURCE_LLM = "llm_extracted"
EXTRACTION_VERSION = 1
MENTIONS_PREDICATE = "mentions"
_LINK_RE = re.compile(r"\]\(([^)\s]+\.md)(?:#[^)]*)?\)")
_STOP_WORDS = frozenset({
    "what", "which", "where", "when", "with", "from", "that", "this", "and", "the",
    "关系", "什么", "哪些", "如何", "相关", "有关",
})


@dataclass(frozen=True)
class GraphRebuildResult:
    indexed_pages: int
    indexed_entities: int
    indexed_relations: int
    db_path: Path


@dataclass(frozen=True)
class IngestResult:
    pages_ingested: int
    entities_upserted: int
    relations_upserted: int
    warnings: Tuple[str, ...]
    db_path: Path


def graph_index_path(bundle_path: Path | str) -> Path:
    """Return the disposable graph cache path for ``bundle_path``."""
    return Path(bundle_path) / ".mneme" / "graph.db"


def graph_extraction_path(bundle_path: Path | str) -> Path:
    """Return the replayable agent-extraction manifest for a bundle."""
    return Path(bundle_path) / ".mneme" / "graph-extractions.json"


def _graph_source_fingerprint(bundle: Path) -> str:
    """Hash the Markdown inputs that contribute deterministic graph rows."""
    digest = hashlib.sha256()
    for path in sorted(bundle.rglob("*.md")):
        if not path.is_file():
            continue
        parts = path.relative_to(bundle).parts
        if any(part in {".mneme", "sources", "external-sources"} for part in parts):
            continue
        if path.name in {"index.md", "log.md"}:
            continue
        digest.update(path.relative_to(bundle).as_posix().encode("utf-8"))
        digest.update(b"\0")
        try:
            digest.update(path.read_bytes())
        except OSError:
            continue
        digest.update(b"\0")
    return digest.hexdigest()


def graph_is_fresh(bundle_path: Path | str, db_path: Path | str | None = None) -> bool:
    """Return whether a graph cache was built from the current Markdown."""
    bundle = Path(bundle_path)
    path = Path(db_path) if db_path is not None else graph_index_path(bundle)
    if not path.is_file():
        return False
    conn = open_graph(path)
    try:
        row = conn.execute("SELECT value FROM meta WHERE key='source_fingerprint'").fetchone()
    except sqlite3.Error:
        return False
    finally:
        conn.close()
    return row is not None and row[0] == _graph_source_fingerprint(bundle)


def open_graph(db_path: Path | str) -> sqlite3.Connection:
    """Open a graph database with foreign-key enforcement enabled."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    """Idempotently add ``column`` to ``table`` for in-place v1 → v2 upgrades."""
    existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


def ensure_graph_schema(conn: sqlite3.Connection) -> None:
    """Create the v4 graph schema and its navigation indexes.

    Schema v3 adds provenance columns: ``source``/``confidence`` on entities
    and ``source``/``confidence``/``evidence`` on relations. Existing v1
    databases are upgraded in place via idempotent ALTERs; the Markdown
    bundle remains the only source of truth, so a full ``reindex --graph``
    rebuild repopulates every provenance value deterministically.
    """
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

        CREATE TABLE IF NOT EXISTS relation_sources (
            relation_id INTEGER NOT NULL REFERENCES relations(id) ON DELETE CASCADE,
            source_page TEXT NOT NULL,
            source      TEXT NOT NULL DEFAULT '',
            confidence  REAL,
            evidence    TEXT,
            PRIMARY KEY(relation_id, source_page, source)
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
        CREATE INDEX IF NOT EXISTS idx_relation_sources_page ON relation_sources(source_page, source);
        CREATE INDEX IF NOT EXISTS idx_communities_entity ON communities(entity_id);
        CREATE INDEX IF NOT EXISTS idx_communities_comm   ON communities(community_id);
        """
    )
    _ensure_column(conn, "entities", "source", "source TEXT NOT NULL DEFAULT ''")
    _ensure_column(conn, "entities", "confidence", "confidence REAL")
    _ensure_column(conn, "relations", "source", "source TEXT NOT NULL DEFAULT ''")
    _ensure_column(conn, "relations", "confidence", "confidence REAL")
    _ensure_column(conn, "relations", "evidence", "evidence TEXT")
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


def _read_extraction_manifest(bundle: Path) -> Dict[str, Any]:
    path = graph_extraction_path(bundle)
    if not path.is_file():
        return {"version": EXTRACTION_VERSION, "pages": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError):
        return {"version": EXTRACTION_VERSION, "pages": []}
    pages, _ = validate_extraction(payload)
    return {"version": EXTRACTION_VERSION, "pages": pages}


def _write_extraction_manifest(bundle: Path, pages: Sequence[Dict[str, Any]]) -> None:
    path = graph_extraction_path(bundle)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = _read_extraction_manifest(bundle)
    by_page = {item["page"]: item for item in existing["pages"]}
    by_page.update({item["page"]: item for item in pages})
    payload = {"version": EXTRACTION_VERSION, "pages": [by_page[key] for key in sorted(by_page)]}
    temp = path.with_name(f"{path.name}.tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with temp.open("rb") as handle:
        os.fsync(handle.fileno())
    os.replace(temp, path)


def upsert_entity(
    conn: sqlite3.Connection,
    name: str,
    entity_type: str = "concept",
    *,
    page_path: str | None = None,
    description: str | None = None,
    properties: Dict[str, Any] | None = None,
    source: str = "",
    confidence: float | None = None,
) -> int:
    """Insert or update an entity and return its integer id.

    Page entities are keyed by ``page_path`` so two pages may share a title.
    Other entities use the schema's ``(name, entity_type)`` uniqueness rule.
    ``source`` records provenance (``page``/``tag``/``llm_extracted``) and is
    never downgraded: an llm_extracted entity refreshed by a deterministic
    rebuild keeps its richer description, while provenance moves to the
    latest writer. ``confidence`` is the extractor's 0..1 score (NULL for
    deterministic rows).
    """
    name = str(name or "").strip()
    entity_type = str(entity_type or "concept").strip() or "concept"
    if not name:
        raise ValueError("entity name must not be empty")
    bounded_confidence = None if confidence is None else max(0.0, min(1.0, float(confidence)))
    if entity_type == PAGE_ENTITY_TYPE and page_path:
        row = conn.execute(
            "SELECT id FROM entities WHERE entity_type=? AND page_path=?",
            (entity_type, page_path),
        ).fetchone()
        if row is not None:
            conn.execute(
                "UPDATE entities SET name=?, description=?, properties=?, source=?, confidence=?, updated_at=datetime('now') WHERE id=?",
                (name, description or "", _json(properties), source, bounded_confidence, row[0]),
            )
            return int(row[0])
    conn.execute(
        """
        INSERT INTO entities(name, entity_type, page_path, description, properties, source, confidence)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(name, entity_type) DO UPDATE SET
            page_path=COALESCE(excluded.page_path, entities.page_path),
            description=COALESCE(NULLIF(excluded.description, ''), entities.description),
            properties=COALESCE(excluded.properties, entities.properties),
            source=excluded.source,
            confidence=COALESCE(excluded.confidence, entities.confidence),
            updated_at=datetime('now')
        """,
        (name, entity_type, page_path, description or "", _json(properties), source, bounded_confidence),
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
    source: str = "",
    confidence: float | None = None,
    evidence: str | None = None,
) -> int:
    """Insert or refresh a directed relation and return its id."""
    predicate = str(predicate or "relates_to").strip() or "relates_to"
    bounded_weight = max(0.0, min(1.0, float(weight)))
    bounded_confidence = None if confidence is None else max(0.0, min(1.0, float(confidence)))
    conn.execute(
        """
        INSERT INTO relations(subject_id, predicate, object_id, weight, source_page, properties, source, confidence, evidence)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(subject_id, predicate, object_id) DO UPDATE SET
            weight=excluded.weight,
            source_page=excluded.source_page,
            properties=excluded.properties,
            source=excluded.source,
            confidence=COALESCE(excluded.confidence, relations.confidence),
            evidence=COALESCE(excluded.evidence, relations.evidence)
        """,
        (subject_id, predicate, object_id, bounded_weight, source_page, _json(properties),
         source, bounded_confidence, evidence),
    )
    row = conn.execute(
        "SELECT id FROM relations WHERE subject_id=? AND predicate=? AND object_id=?",
        (subject_id, predicate, object_id),
    ).fetchone()
    if row is None:  # pragma: no cover - sqlite would have raised above
        raise RuntimeError("failed to upsert graph relation")
    relation_id = int(row[0])
    if source_page:
        conn.execute(
            """
            INSERT INTO relation_sources(relation_id, source_page, source, confidence, evidence)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(relation_id, source_page, source) DO UPDATE SET
                confidence=excluded.confidence,
                evidence=excluded.evidence
            """,
            (relation_id, source_page, source, bounded_confidence, evidence),
        )
    return relation_id


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
        except (OSError, UnicodeDecodeError):
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
            if raw.startswith("/"):
                target = raw.lstrip("/")
            else:
                target = (path.parent / raw).as_posix()
                target = os.path.normpath(target)
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
                source=ENTITY_SOURCE_PAGE,
            )
        for record in records:
            subject_id = page_ids[record["path"]]
            for tag in record["tags"]:
                tag_id = upsert_entity(conn, tag, TAG_ENTITY_TYPE, description=tag, source=ENTITY_SOURCE_TAG)
                upsert_relation(
                    conn,
                    subject_id,
                    "tagged_by",
                    tag_id,
                    source_page=record["path"],
                    source=REL_SOURCE_TAG,
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
                        source=ENTITY_SOURCE_PAGE,
                    )
                upsert_relation(
                    conn,
                    subject_id,
                    "relates_to",
                    object_id,
                    source_page=record["path"],
                    source=REL_SOURCE_LINK,
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
                "source_fingerprint": _graph_source_fingerprint(root),
            },
        )
        conn.commit()
        conn.close()
        conn = None
        manifest = _read_extraction_manifest(root)
        if manifest["pages"]:
            ingest_extraction(temp_path, manifest, persist=False)
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


def _normalize_predicate(value: Any) -> str:
    """Normalize an extracted predicate to a safe lowercase token."""
    token = re.sub(r"[^0-9A-Za-z_\-一-鿿]+", "_", str(value or "").strip().lower())
    token = token.strip("_")
    return (token or "relates_to")[:64]


def _clamp_confidence(value: Any) -> float | None:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return None


def validate_extraction(payload: Any) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Validate an agent-produced extraction payload (tolerant consumer).

    Returns ``(pages, warnings)``. Per OKF §9 tolerance, malformed blocks are
    skipped with warnings rather than rejecting the whole payload; unknown
    keys are preserved through to storage.
    """
    warnings: List[str] = []
    if not isinstance(payload, dict):
        return [], ["payload is not a JSON object"]
    version = payload.get("version", EXTRACTION_VERSION)
    if version != EXTRACTION_VERSION:
        warnings.append(f"unsupported extraction version {version!r}; expected {EXTRACTION_VERSION}")
    raw_pages = payload.get("pages")
    if not isinstance(raw_pages, list):
        return [], ["payload has no 'pages' list"]
    pages: List[Dict[str, Any]] = []
    for index, block in enumerate(raw_pages):
        if not isinstance(block, dict):
            warnings.append(f"pages[{index}] is not an object; skipped")
            continue
        page = str(block.get("page", "") or "").strip().lstrip("/")
        if not page.endswith(".md"):
            warnings.append(f"pages[{index}] has invalid page {block.get('page')!r}; skipped")
            continue
        entities: List[Dict[str, Any]] = []
        for e_index, entity in enumerate(block.get("entities") or []):
            if not isinstance(entity, dict):
                warnings.append(f"pages[{index}].entities[{e_index}] is not an object; skipped")
                continue
            name = str(entity.get("name", "") or "").strip()
            if not name:
                warnings.append(f"pages[{index}].entities[{e_index}] has empty name; skipped")
                continue
            entities.append({
                "name": name,
                "type": str(entity.get("type", "") or "concept").strip() or "concept",
                "description": str(entity.get("description", "") or ""),
                "confidence": _clamp_confidence(entity.get("confidence")),
            })
        relations: List[Dict[str, Any]] = []
        for r_index, relation in enumerate(block.get("relations") or []):
            if not isinstance(relation, dict):
                warnings.append(f"pages[{index}].relations[{r_index}] is not an object; skipped")
                continue
            subject = str(relation.get("subject", "") or "").strip()
            obj = str(relation.get("object", "") or "").strip()
            if not subject or not obj or subject == obj:
                warnings.append(f"pages[{index}].relations[{r_index}] has empty/self subject/object; skipped")
                continue
            relations.append({
                "subject": subject,
                "predicate": _normalize_predicate(relation.get("predicate")),
                "object": obj,
                "subject_type": str(relation.get("subject_type", "") or "concept").strip() or "concept",
                "object_type": str(relation.get("object_type", "") or "concept").strip() or "concept",
                "confidence": _clamp_confidence(relation.get("confidence")),
                "evidence": str(relation.get("evidence", "") or "")[:500],
            })
        pages.append({"page": page, "entities": entities, "relations": relations})
    return pages, warnings


def ingest_extraction(
    db_path: Path | str,
    payload: Any,
    *,
    persist: bool = True,
) -> IngestResult:
    """Merge agent-extracted entities/relations into ``graph.db``.

    Deterministic counterpart of the agent's LLM extraction (v4 Phase 2).
    Re-ingesting a page replaces that page's prior llm_extracted relations,
    so the operation is idempotent per page. Entities are shared across
    pages and are never deleted here. Extracted entities connect back to
    their page via ``page -mentions-> entity`` edges so BFS traversal from
    an entity seed reaches the source page within one hop.
    """
    live_path = Path(db_path)
    if not live_path.is_file():
        raise FileNotFoundError(f"graph index missing: {live_path}; run `mneme reindex --graph` first")
    pages, warnings = validate_extraction(payload)
    conn = open_graph(live_path)
    entities_upserted = 0
    relations_upserted = 0
    pages_ingested = 0
    try:
        ensure_graph_schema(conn)
        for block in pages:
            page = block["page"]
            page_row = conn.execute(
                "SELECT id FROM entities WHERE entity_type=? AND page_path=?",
                (PAGE_ENTITY_TYPE, page),
            ).fetchone()
            if page_row is None:
                warnings.append(f"page {page!r} not in graph; skipped (run reindex --graph)")
                continue
            page_id = int(page_row[0])
            # Idempotency: drop this page's previous llm_extracted relations.
            conn.execute(
                "DELETE FROM relation_sources WHERE source_page=? AND source=?",
                (page, REL_SOURCE_LLM),
            )
            conn.execute(
                """
                DELETE FROM relations
                WHERE source=? AND NOT EXISTS (
                    SELECT 1 FROM relation_sources rs WHERE rs.relation_id=relations.id
                )
                """,
                (REL_SOURCE_LLM,),
            )
            entity_ids: Dict[str, int] = {}
            for entity in block["entities"]:
                entity_id = upsert_entity(
                    conn,
                    entity["name"],
                    entity["type"],
                    description=entity["description"],
                    properties={"extracted_from": page},
                    source=ENTITY_SOURCE_LLM,
                    confidence=entity["confidence"],
                )
                entity_ids[entity["name"]] = entity_id
                entities_upserted += 1
                upsert_relation(
                    conn,
                    page_id,
                    MENTIONS_PREDICATE,
                    entity_id,
                    weight=entity["confidence"] if entity["confidence"] is not None else 1.0,
                    source_page=page,
                    source=REL_SOURCE_LLM,
                    confidence=entity["confidence"],
                )
                relations_upserted += 1
            for relation in block["relations"]:
                subject_id = entity_ids.get(relation["subject"])
                if subject_id is None:
                    subject_id = upsert_entity(
                        conn, relation["subject"], relation["subject_type"],
                        source=ENTITY_SOURCE_LLM,
                    )
                    entity_ids[relation["subject"]] = subject_id
                    entities_upserted += 1
                    upsert_relation(
                        conn, page_id, MENTIONS_PREDICATE, subject_id,
                        source_page=page, source=REL_SOURCE_LLM,
                    )
                    relations_upserted += 1
                object_id = entity_ids.get(relation["object"])
                if object_id is None:
                    object_id = upsert_entity(
                        conn, relation["object"], relation["object_type"],
                        source=ENTITY_SOURCE_LLM,
                    )
                    entity_ids[relation["object"]] = object_id
                    entities_upserted += 1
                    upsert_relation(
                        conn, page_id, MENTIONS_PREDICATE, object_id,
                        source_page=page, source=REL_SOURCE_LLM,
                    )
                    relations_upserted += 1
                upsert_relation(
                    conn,
                    subject_id,
                    relation["predicate"],
                    object_id,
                    weight=relation["confidence"] if relation["confidence"] is not None else 1.0,
                    source_page=page,
                    source=REL_SOURCE_LLM,
                    confidence=relation["confidence"],
                    evidence=relation["evidence"] or None,
                )
                relations_upserted += 1
            pages_ingested += 1
        conn.commit()
        _write_meta(conn, {
            "indexed_entities": conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0],
            "indexed_relations": conn.execute("SELECT COUNT(*) FROM relations").fetchone()[0],
        })
    finally:
        conn.close()
    if persist and pages_ingested:
        bundle = live_path.parent.parent
        _write_extraction_manifest(bundle, pages)
    return IngestResult(pages_ingested, entities_upserted, relations_upserted, tuple(warnings), live_path)


def _row_to_entity(row: sqlite3.Row) -> Dict[str, Any]:
    item = dict(row)
    item["properties"] = _properties(item.get("properties"))
    return item


def _entity_match_score(item: Dict[str, Any], term: str, full_query: str) -> float:
    """Rank full-query evidence above incidental token overlap."""
    folded = term.casefold()
    is_full_query = folded == full_query.casefold()
    name = str(item.get("name", "")).casefold()
    page_path = str(item.get("page_path", "") or "").casefold()
    description = str(item.get("description", "") or "").casefold()
    properties = json.dumps(
        item.get("properties", {}), ensure_ascii=False, sort_keys=True,
    ).casefold()

    if name == folded:
        return 1.0 if is_full_query else 0.72
    if description == folded:
        return 0.95 if is_full_query else 0.65
    if name.startswith(folded):
        return 0.88 if is_full_query else 0.62
    if description.startswith(folded):
        return 0.82 if is_full_query else 0.52
    if folded in name:
        return 0.78 if is_full_query else 0.48
    if folded in description:
        return 0.74 if is_full_query else 0.40
    if folded in properties:
        return 0.64 if is_full_query else 0.34
    if folded in page_path:
        return 0.30
    return 0.0


def find_entity_by_name(conn: sqlite3.Connection, query: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Find entities using the full query and simple mention tokens.

    Searches ``name``, ``page_path``, ``description``, and ``properties``.
    The ``description`` column carries the OKF frontmatter description
    (often the first prose line of the page), so excluding it caused Graph
    search to miss obvious entity mentions for pages whose name is just a
    path or slug. ``name`` exact matches rank first, then ``name`` prefix
    matches, then full-query description evidence. Token-only overlap is
    deliberately weaker so common words cannot crowd an exact description
    match out of the seed limit.
    """
    terms: List[str] = []
    raw = str(query or "").strip()
    if raw:
        terms.append(raw)
        terms.extend(
            token for token in re.findall(r"[\w\u3400-\u9fff.-]+", raw)
            if token.casefold() not in _STOP_WORDS and token not in terms
        )
    found: Dict[int, Dict[str, Any]] = {}
    for term in terms:
        pattern = f"%{term.casefold()}%"
        rows = conn.execute(
            """
            SELECT id, name, entity_type, page_path, description, properties
            FROM entities
            WHERE lower(name) LIKE ?
               OR lower(COALESCE(page_path, '')) LIKE ?
               OR lower(COALESCE(description, '')) LIKE ?
               OR lower(COALESCE(properties, '')) LIKE ?
            ORDER BY CASE WHEN lower(name)=? THEN 0
                          WHEN lower(name) LIKE ? THEN 1
                          ELSE 2 END, name
            LIMIT ?
            """,
            (pattern, pattern, pattern, pattern,
             term.casefold(), f"{term.casefold()}%", limit),
        ).fetchall()
        for row in rows:
            item = _row_to_entity(row)
            item["_match_score"] = _entity_match_score(item, term, raw)
            entity_id = int(row[0])
            if entity_id not in found or item["_match_score"] > found[entity_id]["_match_score"]:
                found[entity_id] = item
    return sorted(
        found.values(),
        key=lambda item: (-item["_match_score"], str(item.get("name", ""))),
    )[:limit]


def find_relation_evidence(conn: sqlite3.Connection, query: str) -> Dict[str, Dict[str, Any]]:
    """Return source pages for relation triples stated by the query."""
    folded_query = str(query or "").casefold()
    if not folded_query:
        return {}
    rows = conn.execute(
        """
        SELECT s.name, r.predicate, o.name, r.source_page,
               COALESCE(r.confidence, r.weight, 1.0)
        FROM relations r
        JOIN entities s ON s.id = r.subject_id
        JOIN entities o ON o.id = r.object_id
        WHERE r.source_page IS NOT NULL AND r.source_page != ''
        """
    ).fetchall()
    evidence: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        subject, predicate, obj, source_page = (str(row[index] or "") for index in range(4))
        if not subject or not predicate or not obj:
            continue
        if not all(value.casefold() in folded_query for value in (subject, predicate, obj)):
            continue
        score = max(0.0, min(1.0, float(row[4])))
        current = evidence.get(source_page)
        if current is None or score > current["score"]:
            evidence[source_page] = {
                "score": score,
                "relation": f"{subject} {predicate} {obj}",
            }
    return evidence


def bfs_neighborhood(
    conn: sqlite3.Connection,
    seed_ids: Sequence[int],
    depth: int = 2,
    seed_scores: Dict[int, float] | None = None,
) -> Dict[str, Any]:
    """Traverse relations in both directions with edge-aware confidence."""
    depth = max(0, min(int(depth), 8))
    distances = {int(entity_id): 0 for entity_id in seed_ids}
    scores = {
        int(entity_id): float((seed_scores or {}).get(int(entity_id), 1.0))
        for entity_id in seed_ids
    }
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
            edge_score = max(0.0, min(1.0, float(row[4])))
            decay = 0.5
            if row[2] == "tagged_by":
                tag_id = int(row[3])
                degree = int(conn.execute(
                    "SELECT COUNT(*) FROM relations WHERE predicate='tagged_by' AND object_id=?",
                    (tag_id,),
                ).fetchone()[0])
                edge_score *= 1.0 / max(1.0, degree ** 0.5)
            elif row[2] == MENTIONS_PREDICATE:
                # An extracted entity is directly supported by its source
                # page. Preserve that evidence path more strongly than an
                # arbitrary graph hop while still applying edge confidence.
                decay = 0.8
            candidate_score = scores[current] * edge_score * decay
            if neighbor not in distances:
                distances[neighbor] = current_depth + 1
                scores[neighbor] = candidate_score
                queue.append(neighbor)
            elif candidate_score > scores.get(neighbor, 0.0):
                scores[neighbor] = candidate_score
    return {"distances": distances, "scores": scores, "relations": list(relation_rows.values())}


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
        relation_evidence = find_relation_evidence(conn, query)
        if not seeds and not relation_evidence:
            return []
        seed_scores = {int(item["id"]): float(item.get("_match_score", 1.0)) for item in seeds}
        neighborhood = bfs_neighborhood(
            conn, [int(item["id"]) for item in seeds], depth, seed_scores=seed_scores
        )
        distances = neighborhood["distances"]
        rows = conn.execute(
            "SELECT id, name, entity_type, page_path, description, properties FROM entities WHERE entity_type=?",
            (PAGE_ENTITY_TYPE,),
        ).fetchall()
        seed_names = {int(item["id"]): item["name"] for item in seeds}
        candidates = []
        for row in rows:
            entity_id = int(row[0])
            page_path = str(row[3] or "")
            relation_match = relation_evidence.get(page_path)
            if entity_id not in distances and relation_match is None:
                continue
            entity = _row_to_entity(row)
            if entity["properties"].get("missing"):
                continue
            entity["distance"] = 0 if relation_match is not None else distances[entity_id]
            entity["graph_score"] = max(
                float(neighborhood["scores"].get(entity_id, 0.0)),
                float(relation_match["score"]) if relation_match is not None else 0.0,
            )
            entity["matched_entities"] = [
                name for seed_id, name in seed_names.items() if distances.get(seed_id) == 0
            ]
            if relation_match is not None:
                entity["matched_entities"].append(relation_match["relation"])
            candidates.append(entity)
        candidates.sort(key=lambda item: (-item["graph_score"], item["distance"], item["page_path"] or item["name"]))
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
        llm_entity_count = int(
            conn.execute("SELECT COUNT(*) FROM entities WHERE source=?", (ENTITY_SOURCE_LLM,)).fetchone()[0]
        )
        llm_relation_count = int(
            conn.execute("SELECT COUNT(*) FROM relations WHERE source=?", (REL_SOURCE_LLM,)).fetchone()[0]
        )
        return {
            "schema_version": meta.get("schema_version", GRAPH_SCHEMA_VERSION),
            "entity_count": entity_count,
            "relation_count": relation_count,
            "orphan_entity_count": orphan_count,
            "unresolved_page_count": unresolved_count,
            "connected_component_count": components,
            "llm_entity_count": llm_entity_count,
            "llm_relation_count": llm_relation_count,
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
