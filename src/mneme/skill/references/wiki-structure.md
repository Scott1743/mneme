---
type: Reference
title: mneme wiki structure
description: How a growing OKF wiki bundle is organized and curated.
---
# wiki structure

A bundle:

```
<bundle>/
├── index.md          # root index (progressive disclosure; root has okf_version)
├── log.md            # change timeline (## YYYY-MM-DD <op> | <title>)
├── sources/          # immutable raw source copies (ingest copies here)
├── concepts/         # atomic concept pages (the bulk; flat + slug)
├── references/       # distilled external sources (papers/articles)
├── summaries/        # cross-concept syntheses (compaction products)
├── topics/           # topical hubs (curated reading paths/maps)
├── archive/          # superseded pages (kept for history, de-indexed)
└── .mneme/           # derived (L2 index.db) — gitignored, not OKF concepts
```

Curation: one concept per page; slug = lowercase, non-alnum→hyphen; cross-links absolute bundle-relative (`/dir/concept.md`); at thresholds roll multiple pages into a `summaries/` page; retire stale to `archive/` (de-indexed); use `topics/` for curated entry points. Retrieval is via the L2 index, so the tree stays flat — no manual deep nesting.
