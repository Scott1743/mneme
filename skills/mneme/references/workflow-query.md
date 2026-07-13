---
type: Reference
title: mneme query workflow (host-agent)
description: Detailed checklist for the query scenario in SKILL.md.
---
# query workflow (host-agent)

The query scenario in SKILL.md walks the OKF graph: CLI search → top-k → read each page → synthesize with bundle-relative citations.

1. **Search** with `python3 ~/.claude/skills/mneme/scripts/mneme.py search "<question>" --json -k 10`. Pass the question as an argv value, never as generated Python source. L2 use is opt-in: the user runs `pip install 'sqlite-vec>=0.1.9,<0.2' 'fastembed>=0.8.0,<0.9'` once; the skill itself does not auto-install.
2. **KNN** is performed by the derived sqlite-vec index using fastembed (default `BAAI/bge-small-zh-v1.5`).
3. **Read** each top chunk's full concept page.
4. **Synthesize** an answer with **inline citations** as bundle-relative links: `[/concepts/foo.md]([/concepts/foo.md)`.
5. **Honest gaps**: if the wiki lacks coverage, say so and recommend `ingest`.
6. **Backfill offer**: if your synthesized answer is broadly useful and no page covers it, OFFER to write it as a new `Summary` page (ask first; do not auto-write).

`search` alone returns ranked snippets. `query` must read the complete Markdown pages before answering because the OKF bundle, not SQLite chunks, is the source of truth.
