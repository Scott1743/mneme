---
type: Reference
title: mneme search workflow (host-agent synthesis)
description: Retrieve candidates, read authoritative pages, and answer with bundle citations.
---

# search workflow

1. Read the bundle's root `index.md` and follow relevant titles, tags, and
   links. A missing index is tolerated; use local file/text discovery instead.
2. When ranking helps, run
   `python3 ~/.claude/skills/mneme/scripts/mneme.py search "<question>" --json -k 10`.
   Treat the question as an argument value, never generated source code.
3. Review candidate paths and snippets, then read every relevant Markdown page
   in full. The bundle is authoritative; the SQLite index is disposable.
4. Synthesize across those pages and cite claims with bundle-relative links,
   for example `[Example](/concepts/example.md)`.
5. State missing or conflicting coverage. Do not fill wiki gaps from unstated
   model knowledge.
6. Search never changes the bundle. Offer a separate, preview-and-approval
   `dream` when the user wants to retain a useful synthesis.
