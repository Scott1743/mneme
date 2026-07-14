---
type: Reference
title: mneme search workflow (host-agent synthesis)
description: Retrieve candidates, read authoritative pages, and answer with bundle citations.
---

# search workflow

1. Read the bundle's root `index.md` and follow relevant titles, tags, and
   links. A missing index is tolerated; use local file/text discovery instead.
2. Use the persisted retrieval mode when ranking helps:
   `python3 ~/.claude/skills/mneme/scripts/mneme.py search "<question>" --json -k 10`.
   Treat the question as an argument value, never generated source code.
3. Only for explicitly requested semantic recall, first load
   `index-design.md`, ensure the user has installed the dependencies, then run
   `reindex --l2` once. It persists L2 for later bare `search` commands.
   `reindex --fts5` explicitly returns to FTS5; never silently fall back between modes, and report an unavailable active L2 as an error.
4. Review candidates, then read every relevant Markdown page in full. The
   bundle is authoritative; snippets, chunks, and distances are navigation.
5. Synthesize across those pages and cite claims with bundle-relative links,
   for example `[Example](/concepts/example.md)`.
6. State missing or conflicting coverage. Do not fill wiki gaps from unstated
   model knowledge.
7. Search never changes the bundle. Offer a separate, preview-and-approval
   `dream` when the user wants to retain a useful synthesis.
