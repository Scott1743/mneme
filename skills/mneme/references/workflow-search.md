---
type: Reference
title: mneme search workflow (host-agent synthesis)
description: Retrieve candidates, read authoritative pages, and answer with bundle citations.
---

# search workflow

1. Read the bundle's root `index.md` and follow relevant titles, tags, and
   links. A missing index is tolerated; use local file/text discovery instead.
2. Use default FTS5 when ranking helps:
   `python3 ~/.claude/skills/mneme/scripts/mneme.py search "<question>" --json -k 10`.
   Treat the question as an argument value, never generated source code.
3. Only for explicitly requested semantic recall, use the matching explicit
   pair `reindex --l2` and `search --l2`. Never assume an FTS5 index contains
   vectors and never silently fall back between modes.
4. Review candidates, then read every relevant Markdown page in full. The
   bundle is authoritative; snippets, chunks, and distances are navigation.
5. Synthesize across those pages and cite claims with bundle-relative links,
   for example `[Example](/concepts/example.md)`.
6. State missing or conflicting coverage. Do not fill wiki gaps from unstated
   model knowledge.
7. Search never changes the bundle. Offer a separate, preview-and-approval
   `dream` when the user wants to retain a useful synthesis.
