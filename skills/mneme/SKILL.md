---
name: mneme
description: "Maintain and search a local, OKF-conformant LLM knowledge wiki of research/learning notes. Use when the user wants to ingest a source, search or query the wiki, lint it, reindex it, or initialize a wiki. Triggers: 'mneme', 'my wiki', 'search my wiki', 'ingest this', 'query my notes', 'lint the wiki', 'knowledge base', '查 wiki', '搜索知识库', '摄入笔记', '知识库'. Dream (scheduled auto-curation) is intentionally absent from v0.3.0 — see CHANGELOG for the freeze context."
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
  - AskUserQuestion
---

# mneme — lightweight LLM wiki

You drive all mneme operations through native tools (Read/Write/Edit/Bash/Glob/Grep) plus a thin CLI (`mneme init` / `mneme reindex` / `mneme search`). **Never** call any independent agent SDK or `@tool` framework — your native tools ARE the agent runtime.

mneme keeps an external OKF v0.1 wiki of research/learning notes. The skill has 7 scenarios; pick the one matching the user's intent.

## Step 0: resolve the bundle (EVERY scenario)

Find the wiki bundle in this order; use the first hit:
1. `~/.config/mneme/config.toml` key `bundle_path`.
2. `MNEME_BUNDLE` env var.
3. An explicit path the user gave.
4. Auto-discover: walk up from cwd for a root `index.md` whose frontmatter contains `okf_version`.
5. `./wiki` if it exists.
6. None found → ask the user for the path, or offer to run `init`.

Helper:
```bash
Bash: python3 -c "import sys; sys.path.insert(0,'./skills/mneme/scripts'); from tools_helpers import resolve_bundle; print(resolve_bundle())"
```

> **Skill-relative paths:** paths like `scripts/validate_okf.py` are relative to this skill's own directory (the folder containing this SKILL.md). Run them from there.

## OKF v0.1 conformance (hard rules — never violate on write)

1. Every non-reserved `.md` MUST have a `---`-delimited YAML frontmatter block.
2. Every frontmatter MUST have a non-empty `type`.
3. Reserved `index.md` (no frontmatter except root `okf_version`) and `log.md` (date-prefixed timeline) follow their structure.

Do NOT reject unknown `type` values, extra frontmatter keys, or broken links — warnings only.

## type vocab (recommended, non-registered)

`Concept` (idea/topic) · `Reference` (distilled external source) · `Summary` (synthesis) · `Source` (raw doc in sources/).

## Scenario: init <path>

Scaffold an OKF bundle + record its location:

1. `Bash: python3 skills/mneme/scripts/mneme.py init <path> [--config <cfg>]` (paths relative to cwd; if absent, `--config` defaults to `~/.config/mneme/config.toml`).
2. Verify: `<path>/index.md` has `okf_version: "0.1"`, `<path>/log.md` exists, `<path>/sources/.gitkeep` exists.
3. Confirm to the user; the bundle path is now discoverable via Step 0.

## Scenario: reindex [--config <cfg>]

Rebuild the L2 sqlite-vec index from scratch:

1. `Bash: python3 skills/mneme/scripts/mneme.py reindex [--config <cfg>]`
2. Confirm the output: `indexed N concepts into <bundle>/.mneme/index.db`.

After every `ingest` or `dream` that adds/removes/merges pages, run `reindex`.

## Scenario: search <query>

Return ranked L2 retrieval hits without synthesizing an answer or modifying the bundle:

1. `Bash: python3 skills/mneme/scripts/mneme.py search "<query>" --json [--type <type>] [-k <limit>]`
2. Present the matching titles, bundle-relative paths, types, and snippets.
3. Do not auto-reindex. If the index is absent or incompatible, report the CLI remedy (`mneme reindex`).

Pass the query as a shell argument, never splice it into Python source. Search snippets are navigation aids; the Markdown concept pages remain authoritative.

## Scenario: ingest <source path>

Distill a source (paper/article/note) into OKF concept pages:

0. **Preserve the raw source (immutable artifact).** Before reading the source for distillation, copy the original file unchanged into `<bundle>/sources/<basename>` so the raw input is preserved as the OKF v0.1 source-of-truth alongside the distilled concept pages. If the destination already exists with different content, abort and ask the user — do not overwrite.
1. `Read <source path>` to get the full text.
2. Decide how to decompose into concept pages (one page per atomic idea; one source may yield 1–15 pages).
3. For each page:
   - `Write <bundle>/concepts/<slug>.md` with frontmatter (`type`/`title`/`description`/`tags`/`timestamp`/`resource`) + body.
   - Cross-link related pages with absolute bundle-relative paths (`/concepts/other.md`).
4. `Edit <bundle>/index.md` — find or create the section heading: if `## <section>` (e.g. `## Concepts`, `## References`, `## Summaries`) already exists, append `* [Title](path) - description` under it; otherwise append a new `## <section>` heading followed by the entry. Use the page's frontmatter `type` to pick the section.
5. `Edit <bundle>/log.md` — **prepend** (insert at top) `## YYYY-MM-DD ingest | <source title>` + one-line note. The OKF v0.1 log contract requires newest-first.
6. `Bash: python3 skills/mneme/scripts/mneme.py reindex` (or directly `python3 -c "import sys,indexlib; sys.path.insert(0,'skills/mneme/scripts'); ...; indexlib.reindex_bundle(bundle, indexlib.default_embed_fn())"`).
7. **On model load failure:** do **not** retry with any substitute function. Surface the failure to the user with the exact error and tell them to install the embedding extras: `pip install 'mneme[index]'`. Production reindex has no substitute.

See `references/workflow-ingest.md` for the detailed checklist.

## Scenario: query <question>

Naive RAG: embed → KNN → top-k → read pages → synthesize answer with citations:

1. `Bash: python3 skills/mneme/scripts/mneme.py search "<question>" --json -k 10`
2. For each top chunk, `Read <bundle>/<chunk.path>` (use `concept_id` from the search result to derive path: `concepts/foo` → `concepts/foo.md`).
3. Synthesize an answer with **inline citations** as bundle-relative markdown links: `[Foo](/concepts/foo.md)`.
4. If the answer is broadly useful and no page covers it, OFFER (do not auto-write) to backfill it as a new `Summary` page.
5. Honest about gaps: if the wiki lacks coverage, say so and suggest an `ingest`.

See `references/workflow-query.md`.

## Scenario: lint

Curate + report (do **not** auto-modify):

1. `Bash: python3 skills/mneme/scripts/validate_okf.py <bundle>` — read ERRORs (must fix) and WARNings.
2. `Bash: python3 -c "import sys; sys.path.insert(0,'skills/mneme/scripts'); import okflib; print(okflib.find_orphans('<bundle>'))"` — orphan concept IDs (not linked from anywhere).
3. Read a sample of pages; look for contradictions / stale timestamps / missing cross-links.
4. Write a curated report to `<bundle>/lint-report-<date>.md` (do **not** modify files; let the user decide).

See `references/workflow-lint.md`.

> **dream (scheduled, fully automatic)** is **intentionally absent** from this skill in v0.3.0. The dream workflow's similarity math referenced a non-existent `find_orphans()` primitive, ran `git add -A` before resolving the bundle, and could auto-commit unrelated user changes. Re-introduction requires: (a) Phase 5 retrieval benchmark passing, (b) `find_orphans` + similarity-safe workflow under test, (c) dry-run preview mode + a dedicated safety TDD suite. See `CHANGELOG.md` 0.2.1 entry.

## references (load on demand)

`scripts/validate_okf.py` (validator) · `references/workflow-ingest.md` · `references/workflow-query.md` · `references/workflow-lint.md` · `references/type-vocab.md` · `references/wiki-structure.md` · `references/index-design.md`.

OKF spec: <https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md>.
