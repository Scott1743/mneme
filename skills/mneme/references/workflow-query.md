---
type: Reference
title: mneme query workflow
description: How to answer questions from the wiki with citations.
---
> The `mneme query <question>` CLI searches the L2 index and synthesizes a cited answer. This doc is the agent's spec. See `wiki-structure.md` + `index-design.md`.

# query workflow

- **Progressive disclosure**: always read `index.md` first; do not load the whole bundle. Drill only into pages the index suggests are relevant.
- **Cite**: every non-trivial claim links the concept page it came from (`/concepts/<id>.md`). If the page has a `# Citations` section, surface those external links too.
- **Honesty about gaps**: if the wiki lacks coverage, say so — do not fabricate. Suggest an ingest.
- **Backfill**: if your synthesized answer is broadly useful and no page covers it, OFFER to create a `Summary` or `Concept` page capturing it (ask first; v1 does not auto-write).
