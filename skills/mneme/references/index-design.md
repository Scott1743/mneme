---
type: Reference
title: mneme index design
description: L2 sqlite-vec + fastembed index — schema, chunking, retrieval.
---
# index design

- **Storage:** `<bundle>/.mneme/index.db` (SQLite + sqlite-vec). gitignored. Derived.
- **Tables:** `chunks(chunk_id, concept_id, path, title, type, chunk_idx, text, tags, timestamp, hash)`; `vec_chunks` (vec0 virtual table, `embedding FLOAT[dim]`); `meta(key, value)` (`dim`, `embedding_model`, `okf_version`, `last_sync`).
- **Embedding:** fastembed ONNX, multilingual small model (e.g. `intfloat/multilingual-e5-small`, 384-dim). Offline, no key. `embed_fn` is injected (testable with a fake).
- **Chunking:** concept pages by markdown headings; sources by paragraph/512-token with overlap.
- **Incremental:** per-chunk hash; unchanged chunks skipped on reindex (mtime/hash fast-path).
- **Query:** embed question → sqlite-vec KNN top-k → join chunk text + concept_id → ranked. `distance` is sqlite-vec's raw distance (for ranking, not a 0–1 similarity).
