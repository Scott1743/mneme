---
type: Reference
title: mneme index design
description: Independent Graph, FTS5, and persistent opt-in semantic indexing.
---

# index design

All indexes use independent disposable, gitignored files. The Markdown bundle
remains authoritative, and each rebuild atomically replaces only its own cache:

- `<bundle>/.mneme/fts.db` for zero-dependency FTS5;
- `<bundle>/.mneme/graph.db` for v4 page/tag/link graph navigation;
- `<bundle>/.mneme/graph-extractions.json` for replaying approved agent graph
  enrichment when `graph.db` is rebuilt;
- `<bundle>/.mneme/l2.db` for explicitly activated semantic retrieval.

The persisted FTS5/L2 choice lives in `~/.config/mneme/config.toml` as
`active_retrieval_mode`. Configurations without that field remain FTS5. When
Graph exists and L2 is not active, bare search uses hybrid Graph + FTS5.
Deleting Graph restores the v3-compatible FTS5/L0 path.

## Default: FTS5

New and pre-L2 configurations use Python's standard-library SQLite FTS5.
`mneme reindex` builds `<bundle>/.mneme/fts.db`; `mneme search` uses it. No
third-party dependency or model is required. Without that index, search may
fall back to a local Markdown scan.

## v4 Graph + hybrid retrieval

`mneme reindex --graph` builds `<bundle>/.mneme/graph.db` from valid OKF
concept pages without changing them. Phase 1 derives:

- one page entity per concept path;
- tag entities plus `tagged_by` relations;
- Markdown-link relations between page entities;
- graph health counters for the read-only `dream --json` report.

After Graph exists, bare search uses hybrid mode: Graph finds entity-related page
paths, FTS5 independently searches the whole bundle, and ranking fuses the union
of both candidate sets. Graph never hard-filters global lexical recall. Each
Graph rebuild records a Markdown source fingerprint; a stale graph is ignored
and hybrid falls back to global FTS5 until `reindex --graph` refreshes it.
`search --mode graph|fts|hybrid` provides an explicit per-query override for
diagnostics; it does not persist a new mode.

Graph is stdlib-only SQLite and contains no authoritative facts. Approved agent
extractions are stored as a replay manifest beside `graph.db`, so rebuilding the
database does not silently discard enrichment. Both files remain derived cache:
Markdown is the authority, and deleting `.mneme/` restores the plain FTS5/L0
behavior without losing wiki content.

`mneme serve` visualizes these provenance layers rather than reconstructing a
page-only graph from Markdown. Its Graph tab can slice the deterministic base
layer and approved enrichment layer, inspect relation confidence/evidence, and
return every entity or relation to its Markdown source pages. The Browse tab
shows the same graph context for the current page. The console's reindex action
can create the base Graph on first use; enrichment still enters only through an
approved `graph ingest` payload.

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

## Upgrade from 3.x

The old `<bundle>/.mneme/index.db` is a disposable derived cache. Version 4.0
does not reuse it: run `mneme reindex` for FTS5, `mneme reindex --graph` for
hybrid graph navigation, or `mneme reindex --l2` to build and activate L2 once.

L2 ranks chunks internally, then collapses them to one best chunk per concept
page before applying top-k. For the default normalized BGE model, an L2 distance
above 1.10 is treated as outside the conservative recall boundary; custom
embedders remain unfiltered because their distance scale is unknown. Returned
raw distances are navigation evidence, not truth. Always read complete Markdown
pages before answering, citing, merging, or proposing curation.
