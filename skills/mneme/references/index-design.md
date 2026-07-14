---
type: Reference
title: mneme index design
description: SQLite FTS5 index — schema, rebuild, and candidate retrieval.
---
# index design

- **Storage:** `<bundle>/.mneme/index.db` (SQLite FTS5). gitignored. Derived.
- **Tables:** `pages(id, path, type, title, description, tags, mtime, body)` plus the synchronized `pages_fts` virtual table.
- **Snapshot rebuild:** `reindex` builds a fresh temporary database and atomically replaces the live index after success. Deleted/moved pages disappear; a failed rebuild preserves the last usable index. Incremental hash-based embedding is deferred.
- **Index policy:** `.mneme/` and `archive/` are excluded. An unreadable individual concept is skipped without making other concepts unavailable.
- **Search:** `python3 ~/.claude/skills/mneme/scripts/mneme.py search <query> --json` returns FTS5 candidates with compact body snippets. Without an index, it scans local Markdown pages.
- **Authority:** candidates are navigation aids. Read the full Markdown page before synthesizing or citing an answer.
