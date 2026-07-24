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

The persisted FTS5/L2 capability choice lives in
`~/.config/mneme/config.toml` as `active_retrieval_mode`. Configurations without
that field remain FTS5. This setting is separate from per-query routing: `auto`
is never stored there. Bare search and `search --mode auto` use Graph + FTS5
when Graph exists. Explicitly activating L2 adds its semantic candidates to
that Hybrid ranking; it does not replace the other legs.

## Auto query routing

Auto is the user-facing name for default query routing, not an index activation
state. It is expressed by omitting `--mode`, by passing `--mode auto`, or by
selecting `mode: auto` in the Web console. All three forms preserve
`active_retrieval_mode` and select the same available legs:

- persisted `fts5`: fresh Graph + FTS5, or FTS5/L0 when Graph is unavailable;
- persisted `l2`: fresh Graph + FTS5 + L2, with remaining active legs continuing
  when Graph is unavailable or stale.

Choosing auto never runs `reindex`, switches L2 activation, or maps auto to
FTS5. `reindex --l2` and `reindex --fts5` remain the only CLI operations that
intentionally change the persisted capability state.

## Default: FTS5

New and pre-L2 configurations use Python's standard-library SQLite FTS5.
`mneme reindex` builds `<bundle>/.mneme/fts.db`; `mneme search` uses it. No
third-party dependency or model is required. Without that index, search may
fall back to a local Markdown scan.

## Hybrid retrieval

`mneme reindex --graph` builds `<bundle>/.mneme/graph.db` from valid OKF
concept pages without changing them. Phase 1 derives:

- one page entity per concept path;
- tag entities plus `tagged_by` relations;
- Markdown-link relations between page entities;
- graph health counters for the read-only `dream --json` report.

After Graph exists, bare search uses hybrid mode: Graph finds entity-related page
paths and FTS5 independently searches the whole bundle. When L2 is active, its
semantic page candidates join the same union. Ranking defaults to 0.75 Graph,
0.10 FTS5, and 0.15 L2. The weights come from an exhaustive 1% grid evaluated
with ten repetitions of grouped five-fold outer validation over 59 base cases.
Against the prior 0.40/0.40/0.20 mix, case-macro MRR improved by 0.027 with a
paired case-cluster 95% interval of [0.013, 0.041]; all exact source-page titles
remained first. Weights renormalize across legs that returned candidates. FTS5
and L2 contribute reciprocal page-rank scores; Graph contributes its normalized
reachability score. Graph never hard-filters global lexical or semantic recall.
Each Graph rebuild records a Markdown source fingerprint; a stale graph is
ignored while the other active legs continue. `search --mode auto` explicitly
requests default routing; `search --mode graph|fts|hybrid|l2` provides per-query
diagnostic overrides. None of these query flags persists a mode.

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
always refreshes FTS5 and Graph; when L2 is active, it rebuilds L2 first and
stops with an explicit error if semantic indexing fails. It can create the base
Graph on first use, while enrichment still enters only through an approved
`graph ingest` payload.

## Explicit opt-in: L2

Only when the user requests semantic recall:

1. The user installs compatible `sqlite-vec` and `fastembed` packages; Mneme
   never installs them.
2. `mneme reindex --l2` builds `<bundle>/.mneme/l2.db` with
   `BAAI/bge-small-zh-v1.5` and persists `active_retrieval_mode = "l2"`; the
   first model download is a user-authorized consequence of that explicit
   command.
3. Later bare `mneme search` adds L2 to full Hybrid, while bare `mneme reindex`
   continues rebuilding the persisted L2 mode. Missing or unavailable active
   L2 reports an error and never silently falls back to Graph or FTS5.
4. `mneme reindex --fts5` explicitly switches the persisted mode back to FTS5.
   It does not delete `l2.db`; changing modes never overwrites the other cache.

## Upgrade from 3.x

The old `<bundle>/.mneme/index.db` is a disposable derived cache. Version 4.0
does not reuse it: run `mneme reindex` for FTS5, `mneme reindex --graph` for
hybrid graph navigation, or `mneme reindex --l2` to build and activate L2 once.

L2 ranks chunks internally, then collapses them to one best chunk per concept
page before applying top-k. For the default normalized BGE model, an L2 distance
above 0.90 is treated as outside the balanced relevance boundary (approximately
cosine similarity 0.595); custom embedders remain unfiltered because their
distance scale is unknown. Returned raw distances are navigation evidence, not
truth. Always read complete Markdown pages before answering, citing, merging,
or proposing curation.
