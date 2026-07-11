# Mneme Search — Design Spec v2.2

- **Date:** 2026-07-11
- **Status:** Implemented
- **Supersedes:** the retrieval/CLI portions of `2026-07-06-mneme-skill-design-v2_1.md`; all OKF, host-agent, and dream decisions remain in force.
- **Problem:** v2.1 has a private `indexlib.search()` function but no stable command-line retrieval interface. The skill therefore embeds an unsafe, hard-to-script `python -c` command, while the public CLI exposes only `init` and `reindex`.

## 1. Outcome

Add a small, read-only retrieval command:

```bash
mneme search <query> [-k N] [--type TYPE] [--config CFG] [--json]
```

`search` returns ranked wiki chunks. It does not synthesize an answer and never writes to the OKF bundle.

Keep `query` as a SKILL.md scenario:

```text
query = search -> read full concept pages -> host agent synthesizes -> cite sources
```

This is the important boundary:

| Surface | Responsibility | Needs semantic judgment | Writes wiki |
|---|---|---:|---:|
| `mneme search` | Deterministic L2 retrieval | No | No |
| SKILL.md `query` | Answer synthesis and gap judgment | Yes, host agent | No; backfill is offer-only |
| SKILL.md `ingest` / `dream` | Knowledge maintenance | Yes, host agent | Yes |

## 2. Why this fits Mneme

The v2.1 rule "CLI only has init/reindex" correctly removed independent agent runtimes, but it grouped two different concerns together:

- `query`, `ingest`, `lint`, and `dream` are workflows requiring host-agent judgment and should remain in SKILL.md.
- `search` is a deterministic, read-only L2 primitive already implemented in Python and should have a stable CLI boundary.

Adding `search` does not reintroduce Strands, an MCP server, a daemon, a cloud dependency, or a second source of truth. L1 Markdown remains authoritative; `.mneme/index.db` remains optional and derived.

OKF v0.1 does not prescribe query infrastructure (SPEC §1 non-goals), so this is a reference-consumer feature, not an OKF extension. Unknown `type` values, optional frontmatter omissions, and broken links remain tolerated.

## 3. Current defects to address first

### 3.1 Missing public retrieval boundary

- `indexlib.search()` exists, but users and agents must import an internal module.
- SKILL.md interpolates the question into `python -c`, which is fragile for quotes/newlines and unsuitable for stable automation.
- Python `repr` output is not a documented machine-readable contract.

### 3.2 `reindex` is not actually a full rebuild

`reindex_bundle()` upserts current concepts but never removes concepts deleted or moved since the prior run. Search can therefore return stale paths.

The v2.1 docs call this a "full rebuild". v2.2 makes that statement true by building a fresh temporary database and atomically replacing the old one only after success.

### 3.3 Archive policy is not enforced

`wiki-structure.md` says `archive/` is de-indexed, but `okflib.list_concepts()` returns archived Markdown and `reindex_bundle()` indexes it. Search can rank retired knowledge as current.

OKF enumeration and search indexing are different concerns. `okflib.list_concepts()` must continue listing all OKF concepts; `indexlib` will apply an explicit index policy that excludes `archive/` and `.mneme/`.

### 3.4 Index metadata is incomplete

The reference design promises `embedding_model`, `okf_version`, and `last_sync`; the implementation stores only vector dimension. A search command cannot reliably explain model mismatch or index freshness without this metadata.

### 3.5 Dependency and index failures are opaque

`open_index()` swallows every sqlite-vec import/load exception. Missing `sqlite-vec`, missing `fastembed`, an absent index, and a corrupt index surface later as unrelated SQLite errors.

The CLI should translate these into concise actionable errors without rejecting the underlying OKF bundle.

### 3.6 Retrieval quality is unmeasured

The only search test asks a hash-based fake embedding to retrieve one exact chunk. It does not cover ranking order, stale deletion, archive exclusion, filters, output format, or failures.

## 4. CLI contract

### 4.1 Usage

```bash
mneme search "attention mechanism"
mneme search "客户画像" -k 5 --type Concept
mneme search "OKF" --json
```

Options:

| Option | Default | Meaning |
|---|---:|---|
| `-k`, `--limit` | `10` | Maximum returned chunks; integer in `1..100` |
| `--type` | none | Exact type filter; unknown values are valid |
| `--config` | default config | Select bundle using the existing resolver |
| `--json` | false | Emit a JSON array for agents/scripts |

No implicit reindex occurs. Search is read-only and predictable. If the index is absent or stale metadata is detected, the command tells the caller to run `mneme reindex`.

### 4.2 Human output

```text
1. Attention Mechanism [Concept]
   concepts/attention-mechanism.md  distance=0.2143
   Attention lets a model weight relevant tokens...
```

### 4.3 JSON output

```json
[
  {
    "rank": 1,
    "concept_id": "concepts/attention-mechanism",
    "path": "concepts/attention-mechanism.md",
    "title": "Attention Mechanism",
    "type": "Concept",
    "text": "# Attention Mechanism\n...",
    "distance": 0.2143
  }
]
```

Paths in CLI results are bundle-relative without a leading slash so callers can open `<bundle>/<path>`. Synthesized Markdown citations continue using absolute bundle-relative links such as `/concepts/attention-mechanism.md`.

### 4.4 Exit codes

| Code | Meaning |
|---:|---|
| `0` | Search completed, including zero hits |
| `1` | Runtime problem: bundle/index/dependency/model mismatch/corruption |
| `2` | Usage error |

## 5. Library boundary

Keep the existing low-level function for tests and internal composition:

```python
search(conn, query, k, embed_fn, concept_type=None) -> list[dict]
```

Add a bundle-level function used by the CLI and SKILL.md:

```python
search_bundle(
    bundle_path,
    query,
    k=10,
    concept_type=None,
    embed_fn=None,
) -> list[dict]
```

`search_bundle()` owns opening the database, checking schema/metadata, creating the default embedder, closing the connection, and normalizing exceptions. This removes storage plumbing from SKILL.md.

Filtering is applied in SQL. When a filter is present, vector KNN should over-fetch a bounded candidate set before filtering so `k` still means "returned hits" rather than "unfiltered candidates". v2.2 supports only exact `type`; tag filtering is deferred until tags are stored structurally.

## 6. Reindex correctness

`reindex_bundle()` becomes a true snapshot rebuild:

1. Resolve all indexable concept IDs.
2. Build `<bundle>/.mneme/index.db.tmp` from an empty schema.
3. Store metadata: schema version, embedding model identifier when known, dimension, OKF target version, indexed concept count, and `last_sync`.
4. Close and fsync the temporary database.
5. Atomically replace `index.db`.
6. On failure, delete the temporary database and preserve the previous usable index.

This favors correctness and simple recovery over premature incremental complexity. At the intended hundreds-of-pages scale, a full rebuild is acceptable. Hash-based incremental indexing remains a future optimization and must not be claimed in the current reference docs.

Index policy:

- Include conforming and parseable non-reserved concepts outside excluded directories.
- Skip `.mneme/` and `archive/`.
- Skip an individually unreadable/non-frontmatter concept without making other concepts unavailable; report the skipped count.
- Do not reject unknown `type`, extra metadata, missing optional fields, or broken links.

## 7. SKILL.md changes

Add a seventh scenario, `search <query>`, for direct retrieval requests. Rewrite `query` to call:

```bash
python3 skills/mneme/scripts/mneme.py search "<question>" --json
```

The host runtime must pass the question as an argv value, not splice it into Python source.

`query` still reads the full concept pages before synthesizing. Search snippets are navigation aids, not authoritative replacements for the Markdown source of truth.

## 8. Documentation consistency

Update these files in the implementation phase:

- `skills/mneme/SKILL.md`
- `skills/mneme/SKILL cn.md`
- `skills/mneme/references/workflow-query.md`
- `skills/mneme/references/index-design.md`
- `AGENTS.md`

`AGENTS.md` currently describes the removed Strands L3 layer and nonexistent `ingest.py` / `query.py` / `lint.py` files. It should describe the v2.1 host-agent architecture plus the v2.2 read-only search CLI.

## 9. Testing

Required tests:

- CLI dispatch, help/usage, bounds checking, human output, and JSON output.
- Queries containing quotes, newlines, Chinese text, and shell metacharacters are passed as data.
- Search returns ranked chunks and supports exact `type` filtering without rejecting unknown types.
- Reindex removes deleted/moved concepts and excludes `archive/`.
- Failed rebuild preserves the prior index.
- Missing index, sqlite-vec, and fastembed produce actionable errors.
- Metadata records model/dimension/schema/last sync and detects mismatch.
- End-to-end: init -> write concepts -> reindex -> CLI search -> validate.

Production-model relevance evaluation is a dogfood test, not a unit test. Use a small fixed Chinese/English corpus and a checked-in query/expected-concept table; do not make tests download models or access the network.

The v2.2 implementation default is `BAAI/bge-small-zh-v1.5`, which is supported by fastembed and matches the initial Chinese corpus. Model identity is stored in index metadata so changing it requires an explicit rebuild.

## 10. Deferred work

- Hybrid lexical/vector ranking (FTS5 or BM25).
- Tag filters and time-range filters.
- Incremental embedding by chunk hash.
- Automatic reindex on search.
- Query answer generation in the CLI.
- MCP server, daemon, remote index, or multiple-bundle management.

Hybrid retrieval should be considered after the first 141-document dogfood run. Proper nouns, filenames, IDs, and acronyms are where vector-only search is most likely to need lexical support; add it based on measured misses, not preemptively.
