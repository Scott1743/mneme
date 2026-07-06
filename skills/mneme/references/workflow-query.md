---
type: Reference
title: mneme query workflow (host-agent)
description: Detailed checklist for the query scenario in SKILL.md.
---
# query workflow (host-agent)

The query scenario in SKILL.md is naive RAG: embed → KNN → top-k → read → synthesize with citations.

1. **Embed** the question (fastembed, default `intfloat/multilingual-e5-small` 384-dim).
2. **KNN** via sqlite-vec `indexlib.search(conn, query, k=10, embed_fn=...)`.
3. **Read** each top chunk's full concept page.
4. **Synthesize** an answer with **inline citations** as bundle-relative links: `[/concepts/foo.md]([/concepts/foo.md)`.
5. **Honest gaps**: if the wiki lacks coverage, say so and recommend `ingest`.
6. **Backfill offer**: if your synthesized answer is broadly useful and no page covers it, OFFER to write it as a new `Summary` page (ask first; do not auto-write).
