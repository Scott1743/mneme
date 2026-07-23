---
type: Reference
title: mneme search workflow (host-agent synthesis)
description: Retrieve candidates, read authoritative pages, and answer with bundle citations.
---

# search workflow

1. Read the bundle's root `index.md` and follow relevant titles, tags, and
   links. A missing index is tolerated; use local file/text discovery instead.
2. Use the active retrieval path when ranking helps:
   `python3 ~/.claude/skills/mneme/scripts/mneme.py search "<question>" --json -k 10`.
   Treat the question as an argument value, never generated source code. Bare
   search uses Graph + FTS5 when Graph exists; after explicit L2 activation it
   adds semantic candidates to the same page-level Hybrid ranking. Build the
   derived graph with `reindex --graph`; this also refreshes FTS5 and never
   changes Markdown.
3. Use `search --mode graph|fts|hybrid|l2` only to diagnose or compare retrieval.
   Graph-only mode requires `graph.db`. Hybrid continues with its other active
   legs when Graph is missing, stale, or has no entity match. Pure L2 mode is a
   per-query diagnostic and does not persist a mode change.
4. Only for explicitly requested semantic recall, first load
   `index-design.md`, ensure the user has installed the dependencies, then run
   `reindex --l2` once. It persists L2 for later full-Hybrid `search` commands.
   `reindex --fts5` explicitly returns to FTS5; never silently fall back between
   an active L2 and the other legs, and report an unavailable active L2 as an error.
5. Review candidates, then read every relevant Markdown page in full. The
   bundle is authoritative; snippets, chunks, graph edges, and distances are navigation.
6. Synthesize across those pages and cite claims with bundle-relative links,
   for example `[Example](/concepts/example.md)`.
7. State missing or conflicting coverage. Do not fill wiki gaps from unstated
   model knowledge.
8. Search never changes the bundle. Offer a separate, preview-and-approval
   `dream` when the user wants to retain a useful synthesis.
