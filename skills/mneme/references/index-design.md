---
type: Reference
title: mneme index design
description: Default FTS5 and explicit opt-in semantic indexing.
---

# index design

Both modes write the disposable, gitignored `<bundle>/.mneme/index.db`. The
Markdown bundle remains authoritative, and rebuilds replace the index
atomically.

## Default: FTS5

`mneme reindex` and `mneme search` use Python's standard-library SQLite FTS5.
No third-party dependency or model is required. Without an index, search may
fall back to a local Markdown scan.

## Explicit opt-in: L2

Only when the user requests semantic recall:

1. The user installs compatible `sqlite-vec` and `fastembed` packages; Mneme
   never installs them.
2. `mneme reindex --l2` builds the vec0 index with
   `BAAI/bge-small-zh-v1.5`; the first model download is a user-authorized
   consequence of that explicit command.
3. `mneme search --l2` requires an L2-built index. It errors on an FTS5-only
   index and never silently falls back.

L2 returns chunks and raw distances for navigation, not truth or calibrated
similarity decisions. Always read complete Markdown pages before answering,
citing, merging, or proposing curation.
