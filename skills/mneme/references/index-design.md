---
type: Reference
title: mneme index design
description: Independent FTS5 and persistent opt-in semantic indexing.
---

# index design

Both modes use independent disposable, gitignored files. The Markdown bundle
remains authoritative, and each rebuild atomically replaces only its own cache:

- `<bundle>/.mneme/fts.db` for default FTS5;
- `<bundle>/.mneme/l2.db` for explicitly activated semantic retrieval.

The active mode lives in `~/.config/mneme/config.toml` as
`active_retrieval_mode`. Configurations without that field remain FTS5.

## Default: FTS5

New and pre-L2 configurations use Python's standard-library SQLite FTS5.
`mneme reindex` builds `<bundle>/.mneme/fts.db`; `mneme search` uses it. No
third-party dependency or model is required. Without that index, search may
fall back to a local Markdown scan.

## Explicit opt-in: L2

Only when the user requests semantic recall:

1. The user installs compatible `sqlite-vec` and `fastembed` packages; Mneme
   never installs them.
2. `mneme reindex --l2` builds `<bundle>/.mneme/l2.db` with
   `BAAI/bge-small-zh-v1.5` and persists `active_retrieval_mode = "l2"`; the
   first model download is a user-authorized consequence of that explicit
   command.
3. Later bare `mneme search` and `mneme reindex` use L2, so an agent cannot
   accidentally change retrieval by forgetting a per-search flag. Missing or
   unavailable L2 reports an error and never silently falls back.
4. `mneme reindex --fts5` explicitly switches the persisted mode back to FTS5.
   It does not delete `l2.db`; changing modes never overwrites the other cache.

## Upgrade from 3.2

The old `<bundle>/.mneme/index.db` is a disposable derived cache. Version 3.3
does not reuse it: run `mneme reindex` for FTS5, or `mneme reindex --l2` to
build and activate L2 once.

L2 returns chunks and raw distances for navigation, not truth or calibrated
similarity decisions. Always read complete Markdown pages before answering,
citing, merging, or proposing curation.
