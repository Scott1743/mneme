---
type: Reference
title: mneme index design
description: L2 sqlite-vec + fastembed index — schema, chunking, retrieval.
---
# index design

- **Storage:** `<bundle>/.mneme/index.db` (SQLite + sqlite-vec). gitignored. Derived.
- **Tables:** `chunks(chunk_id, concept_id, path, title, type, chunk_idx, text, tags, timestamp, hash)`; `vec_chunks` (vec0 virtual table, `embedding FLOAT[dim]`); `meta(key, value)` (`schema_version`, `dim`, `embedding_model`, `okf_version`, `indexed_concepts`, `indexed_chunks`, `last_sync`).
- **Embedding:** fastembed ONNX, default `BAAI/bge-small-zh-v1.5` (512-dim). Local, no API key. `embed_fn` is injected (testable with a fake).
- **Chunking:** concept pages by markdown headings; sources by paragraph/512-token with overlap.
- **Snapshot rebuild:** `reindex` builds a fresh temporary database and atomically replaces the live index after success. Deleted/moved pages disappear; a failed rebuild preserves the last usable index. Incremental hash-based embedding is deferred.
- **Index policy:** `.mneme/` and `archive/` are excluded. An unreadable individual concept is skipped without making other concepts unavailable.
- **Search:** `mneme search <query> --json` embeds the question → sqlite-vec KNN top-k → joins chunk text + concept metadata → ranked results. `distance` is sqlite-vec's raw distance (for ranking, not a 0–1 similarity).
- **Authority:** search chunks are navigation aids. Read the full Markdown page before synthesizing or citing an answer.
