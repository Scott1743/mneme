# Mneme Search v2.2 Implementation Plan

> Implement against `docs/superpowers/specs/2026-07-11-mneme-search-design-v2_2.md` using TDD. Preserve the OKF tolerance contract and keep all agent judgment in SKILL.md.

**Goal:** expose the existing L2 retrieval capability as a stable read-only CLI, make reindex results trustworthy, and align the repository documentation with the actual host-agent architecture.

**Architecture:** L1 Markdown remains the source of truth. `indexlib.py` owns derived L2 storage and retrieval. `mneme.py` exposes `init`, `reindex`, and `search`. SKILL.md composes `search` into the higher-level `query` workflow.

**Dependencies:** Python stdlib for L1/CLI plumbing; `sqlite-vec` + `fastembed` only for L2 semantic indexing/search. No agent SDK, MCP, daemon, cloud service, or build step.

## Global constraints

- Do not edit `.research/upstream/`.
- Do not change any OKF MUST or turn tolerant conditions into hard failures.
- Do not edit the bundle during search.
- Do not auto-reindex during search.
- Keep unknown `type` values searchable.
- Use `apply_patch` for manual edits.
- Do not overwrite the user's untracked `AGENTS.md` blindly; patch only the stale v2 architecture sections after reviewing its current contents.

## Phase A — lock down index correctness

### Task A1: add index policy tests

**Files:** modify `tests/test_indexlib.py`; modify `skills/mneme/scripts/indexlib.py`.

1. Add a failing test that creates current and `archive/` concepts, reindexes, and asserts only current concepts are present.
2. Add a failing test that indexes a concept, deletes or moves it, reindexes, and asserts the old `concept_id` and path are absent.
3. Add a failing test that includes one malformed concept and one valid concept; assert the valid concept remains searchable and the malformed page is counted as skipped.
4. Introduce `iter_indexable_concepts(bundle_path)` in `indexlib.py`. Keep `okflib.list_concepts()` unchanged because archive files are still valid OKF concepts.
5. Run focused tests:

```bash
python3 -m pytest tests/test_indexlib.py -q
```

### Task A2: make reindex an atomic snapshot rebuild

**Files:** modify `skills/mneme/scripts/indexlib.py`; modify `tests/test_indexlib.py`.

1. Add a failing test proving an injected embedding failure leaves the previous `index.db` searchable.
2. Build a new database at a sibling temporary path, never in the live database.
3. Remove any stale temporary file before starting; clean it on failure.
4. Close the SQLite connection before `Path.replace()` atomically installs the new index.
5. Return a structured result such as `ReindexResult(indexed_concepts, indexed_chunks, skipped_concepts, db_path)` instead of an ambiguous integer. Keep a compatibility shim only if existing callers require it during the transition.
6. Update `cmd_reindex` output to report concepts, chunks, and skipped pages.
7. Run index and CLI tests.

### Task A3: record and validate metadata

**Files:** modify `skills/mneme/scripts/indexlib.py`; modify `tests/test_indexlib.py`.

1. Add tests for `schema_version`, `dim`, `embedding_model`, `okf_version`, `indexed_concepts`, and `last_sync`.
2. Give production embedders a stable model identifier without changing the injected `EmbedFn` test seam. A small wrapper/dataclass is preferable to attaching undocumented attributes to arbitrary callables.
3. Add `read_index_meta(conn) -> dict[str, str]`.
4. Detect model/dimension mismatch before running KNN and raise a domain-specific exception with a `mneme reindex` remedy.
5. Keep custom/fake embedders supported for tests.

### Task A4: make dependency failures explicit

**Files:** modify `skills/mneme/scripts/indexlib.py`; modify `tests/test_indexlib.py`.

1. Replace the broad silent `except Exception` around sqlite-vec loading with explicit domain errors while preserving the original cause.
2. Add domain exceptions for missing index, unavailable sqlite-vec, unavailable fastembed, incompatible index, and corrupt index.
3. Ensure these are L2 operational failures only; they must not imply that the OKF bundle is invalid.

## Phase B — add the search service and CLI

### Task B1: extend the low-level search contract

**Files:** modify `skills/mneme/scripts/indexlib.py`; modify `tests/test_indexlib.py`.

1. Add tests for deterministic ordering, zero hits, limit bounds at the library boundary, and exact `type` filtering.
2. Extend `search()` with an optional `concept_type` filter.
3. Use parameterized SQL only.
4. When filtering, over-fetch a bounded number of KNN candidates, apply the filter, and return at most `k`; document that this is post-filtered vector retrieval for v2.2.
5. Add a stable rank field only at the presentation layer, not in stored data.

### Task B2: add `search_bundle()`

**Files:** modify `skills/mneme/scripts/indexlib.py`; modify `tests/test_indexlib.py`.

1. Add failing tests for opening/closing the index, default embedder selection, metadata checks, and normalized results.
2. Implement `search_bundle(bundle_path, query, k=10, concept_type=None, embed_fn=None)`.
3. Reject empty queries and limits outside `1..100` as usage errors.
4. Do not create a missing database as a side effect. Check the path before `sqlite3.connect()`.
5. Always close the connection with `try/finally` or a context manager.

### Task B3: add CLI parsing and output

**Files:** modify `skills/mneme/scripts/mneme.py`; modify `tests/test_cli.py`.

1. Add failing CLI tests for:
   - `search` dispatch and no-argument usage;
   - `-k` / `--limit` validation;
   - `--type` passthrough;
   - `--config` bundle resolution;
   - human output;
   - `--json` parseability and field names;
   - zero hits with exit code `0`;
   - runtime failures with exit code `1`.
2. Replace manual positional scanning with `argparse` subparsers for all three commands. Preserve existing `main(argv) -> int` tests and behavior.
3. Pass the query as argv data. Add regression cases containing `'`, `"`, newlines, `$()`, and Chinese text.
4. Human output includes rank, title, type, bundle-relative path, distance, and a whitespace-normalized bounded snippet.
5. JSON output uses `json.dumps(..., ensure_ascii=False)` and contains no logging noise on stdout. Errors go to stderr.
6. Update top-level usage to `mneme {init,reindex,search}`.

### Task B4: integration test

**Files:** modify `tests/test_integration.py`.

1. Extend the current flow to: init -> write two concepts -> reindex -> invoke `mneme.main(["search", ...])` -> parse JSON -> validate.
2. Assert the returned `path` opens under the bundle.
3. Assert an archived or deleted concept cannot appear after reindex.
4. Keep fake embeddings and a temporary database; tests must not download a model or use the network.

## Phase C — switch the skill to the stable interface

### Task C1: add the `search` scenario

**Files:** modify `skills/mneme/SKILL.md`; modify `skills/mneme/SKILL cn.md`.

1. Change the introduction from six to seven scenarios.
2. Add `Scenario: search <query>` for users who want ranked hits rather than a synthesized answer.
3. Use `mneme.py search ... --json`; do not use `python -c`.
4. State that search is read-only, does not auto-reindex, and returns snippets for navigation.
5. Keep `query` separate: call search, read full pages, synthesize with citations, and offer backfill only when appropriate.
6. Keep both language files behaviorally equivalent.

### Task C2: update retrieval references

**Files:** modify `skills/mneme/references/workflow-query.md`; modify `skills/mneme/references/index-design.md`.

1. Replace direct internal imports with the CLI JSON contract.
2. Remove the unimplemented incremental/hash fast-path claim.
3. Document snapshot rebuild, archive exclusion, metadata, output fields, and failure behavior.
4. Keep the text clear that Markdown pages, not chunks or SQLite rows, are the citation authority.

### Task C3: align project schema documentation

**Files:** modify `AGENTS.md`.

1. Remove the stale Strands L3 runtime and `mneme[agents]` dependency descriptions.
2. Replace nonexistent `tools.py`, `ingest.py`, `query.py`, and `lint.py` layout entries with the actual v2.2 files.
3. Document `mneme search` as a deterministic L2 consumer primitive and `query` as a SKILL.md workflow.
4. Preserve all user-authored OKF constraints and project history outside the stale architecture passages.

### Task C4: supersession notes

**Files:** modify `docs/superpowers/specs/2026-07-06-mneme-skill-design-v2_1.md`; optionally modify `docs/superpowers/plans/2026-07-06-mneme-skill-v2_1.md` only to add a short historical note.

1. Add a prominent note linking to the v2.2 search spec for the CLI/retrieval portions.
2. Do not rewrite historical decisions or erase why the independent agent layer was removed.

## Phase D — verification and dogfood gate

### Task D1: automated verification

1. Install the local development and index extras in an isolated environment if needed:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev,index]'
```

2. Run:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python skills/mneme/scripts/validate_okf.py sample-bundle
.venv/bin/python skills/mneme/scripts/mneme.py --help
```

3. Confirm no test writes a tracked `.mneme/index.db` or modifies sample fixtures.
4. Scan for stale interfaces:

```bash
rg -n "python3? -c.*indexlib.search|CLI only 2|init/reindex only|Strands|mneme\[agents\]|ingest\.py|query\.py|lint\.py" AGENTS.md skills/mneme docs/superpowers/specs
```

### Task D2: offline relevance fixture

**Files:** add `tests/fixtures/search_eval/` and a small manifest; add a non-network evaluation test or script.

1. Create a compact bilingual fixture containing concepts with semantic overlap plus exact identifiers/acronyms.
2. Record queries and expected top concept IDs in JSON.
3. Unit tests use deterministic embeddings only to verify plumbing; mark production-model evaluation as an explicit local dogfood command.
4. Record misses from the 141-document ingest before deciding whether v2.3 needs FTS5/BM25 hybrid retrieval.

## Acceptance criteria

- `mneme search "..."` and `mneme search "..." --json` are stable public interfaces.
- SKILL.md no longer embeds user questions in Python source.
- Reindex cannot return deleted, moved, or archived concepts and cannot destroy the last good index on failure.
- Search failures explain whether the index, sqlite-vec, fastembed, or model compatibility is the problem.
- Unknown types and optional metadata remain tolerated.
- `query` remains host-agent synthesis; no independent runtime is reintroduced.
- Documentation matches the actual repository layout and behavior.
- All tests pass offline after installing declared extras.

## Recommended execution order

Execute A1 -> A2 -> A3 -> A4 -> B1 -> B2 -> B3 -> B4 -> C1 -> C2 -> C3 -> C4 -> D1 -> D2. Do not start hybrid retrieval until the dogfood evaluation demonstrates a concrete need.
