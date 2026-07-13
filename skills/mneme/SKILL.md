---
name: mneme
version: 2.1.0
description: "Maintain and search a local, agent-curated OKF v0.1 Markdown wiki. Use when the user wants to dream (capture knowledge) or search (recall it). Triggers: 'mneme', 'my wiki', 'remember this', 'dream about X', 'search my wiki', '查 wiki', '搜索知识库', '梦', '记住这个'. v2.1 ships skill-first delivery, OKF + tags writer rule, sqlite3 + FTS5 default, `mneme dream` as a read-only audit CLI, and `--l2` opt-in flag for sqlite-vec + FastEmbed + BGE semantic search (FTS5 remains default)."
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

You drive all mneme operations through native tools (Read/Write/Edit/Bash/Glob/Grep) plus a thin CLI shipped inside this skill. **Never** call any independent agent SDK or `@tool` framework — your native tools ARE the agent runtime.

## Skill installation

This skill is delivered via [skill.sh](https://skill.sh) and lands at:

```text
~/.claude/skills/mneme/
├── SKILL.md                    ← you are here
├── SKILL cn.md                 ← 中文版本
├── references/                 ← workflow + spec docs (load on demand)
└── scripts/
    ├── mneme.py                ← CLI entry shim
    └── mneme/                  ← Python package (cli / okflib / indexlib / ...)
```

To invoke the CLI from any Bash block in this skill:

```bash
python3 ~/.claude/skills/mneme/scripts/mneme.py <subcmd> [args]
```

mneme keeps an external OKF v0.1 wiki of research/learning notes. The skill has 7 scenarios; pick the one matching the user's intent.

## Step 0: resolve the bundle (EVERY scenario)

Find the wiki bundle in this order; use the first hit (env-first contract):
1. `$MNEME_BUNDLE` env var.
2. `$HOME/.config/mneme/config.toml` key `[bundle_path]`.
3. Walk up from cwd for a root `index.md` whose frontmatter contains `okf_version`.
4. `./wiki` if it exists.
5. None found → ask the user for the path, or offer to run `init`.

Helper:
```bash
Bash: python3 ~/.claude/skills/mneme/scripts/mneme.py --help
```

> **L2 (semantic search) is opt-in via `--l2`.** v2.1 reintroduces the L2 path (sqlite-vec + FastEmbed + BAAI/bge-small-zh-v1.5) as an **explicit flag** on `reindex` and `search`. Default `reindex` / `search` are still FTS5-only — they require NO third-party deps. Adding `--l2` opts into the L2 path; `reindex --l2` builds the vec0 index with BGE embeddings, `search --l2` queries it. If the L2 deps are missing when `--l2` is used, the CLI prints a one-line install hint (no ImportError traceback): `pip install 'sqlite-vec>=0.1.9,<0.2' 'fastembed>=0.8.0,<0.9'`. **No auto-install, no surprise network calls.** `search --l2` on an FTS5-only index errors out — it never silently falls back to FTS5.

## OKF v0.1 conformance (hard rules — never violate on write)

1. Every non-reserved `.md` MUST have a `---`-delimited YAML frontmatter block.
2. Every frontmatter MUST have a non-empty `type`.
3. Reserved `index.md` (no frontmatter except root `okf_version`) and `log.md` (date-prefixed timeline) follow their structure.

Do NOT reject unknown `type` values, extra frontmatter keys, or broken links — warnings only.

## type vocab (recommended, non-registered)

`Concept` (idea/topic) · `Reference` (distilled external source) · `Summary` (synthesis) · `Source` (raw doc in sources/).

## Scenario: init <path>

Scaffold an OKF bundle + record its location:

1. `Bash: python3 ~/.claude/skills/mneme/scripts/mneme.py init <path> [--config <cfg>]` (paths relative to cwd; if absent, `--config` defaults to `~/.config/mneme/config.toml`).
2. Verify: `<path>/index.md` has `okf_version: "0.1"`, `<path>/log.md` exists, `<path>/sources/.gitkeep` exists.
3. Confirm to the user; the bundle path is now discoverable via Step 0.

## Scenario: reindex [--config <cfg>] [--l2]

Rebuild the search index from scratch. Default is **FTS5** (sqlite3 zero-dep). Add `--l2` to opt into the L2 path (sqlite-vec + FastEmbed + BGE):

1. `Bash: python3 ~/.claude/skills/mneme/scripts/mneme.py reindex [--config <cfg>] [--l2]`
2. Default (FTS5): no extra deps needed; output is `indexed N page(s) into <bundle>/.mneme/index.db`.
3. `--l2`: requires `pip install 'sqlite-vec>=0.1.9,<0.2' 'fastembed>=0.8.0,<0.9'`; the CLI prints a one-line install hint if either is missing. The model download (~90MB) follows on first `--l2` reindex. **No auto-install, no surprise network calls.** Output: `indexed N concept(s) / M chunk(s) into <bundle>/.mneme/index.db (L2: BAAI/bge-small-zh-v1.5)`.

After every `dream` that adds/removes/merges pages, run `reindex` (default or `--l2`, matching whichever path you want to query later).

## Scenario: search <query> [--l2]

Return ranked candidate hits without synthesizing an answer or modifying the bundle. Default is **FTS5**. Add `--l2` to opt into semantic L2 search:

1. `Bash: python3 ~/.claude/skills/mneme/scripts/mneme.py search "<query>" --json [--type <type>] [-k <limit>] [--l2]`
2. Default (FTS5): requires the FTS5 index from `mneme reindex`. If the index is missing, the CLI falls back to L0 grep and nudges on stderr.
3. `--l2`: requires an L2-built index (i.e. `mneme reindex --l2` must have been run). If the index is FTS5-only, the CLI errors with a clear hint — it never silently falls back to FTS5.
4. Present the matching titles, bundle-relative paths, types, and snippets.
5. Do not auto-reindex. If the index is absent or incompatible, report the CLI remedy (`python3 ~/.claude/skills/mneme/scripts/mneme.py reindex` or `reindex --l2`).

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
6. `Bash: python3 ~/.claude/skills/mneme/scripts/mneme.py reindex`.
7. **On model load failure:** do **not** retry with any substitute function and do NOT run pip on the user's behalf. L2 deps are user opt-in; the CLI prints a one-line install instruction; the user runs it.

See `references/workflow-ingest.md` for the detailed checklist.

## Scenario: query <question>

Walk the OKF graph: search returns ranked candidates → read each page in full → synthesize with bundle-relative citations:

1. `Bash: python3 ~/.claude/skills/mneme/scripts/mneme.py search "<question>" --json -k 10`
2. For each top chunk, `Read <bundle>/<chunk.path>` (use `concept_id` from the search result to derive path: `concepts/foo` → `concepts/foo.md`).
3. Synthesize an answer with **inline citations** as bundle-relative markdown links: `[Foo](/concepts/foo.md)`.
4. If the answer is broadly useful and no page covers it, OFFER (do not auto-write) to backfill it as a new `Summary` page.
5. Honest about gaps: if the wiki lacks coverage, say so and suggest an `ingest`.

See `references/workflow-query.md`.

## Scenario: lint

Curate + report (do **not** auto-modify):

1. `Bash: python3 ~/.claude/skills/mneme/scripts/mneme.py lint <bundle>` — read ERRORs (must fix) and WARNings.
2. Read a sample of pages; look for contradictions / stale timestamps / missing cross-links.
3. Write a curated report to `<bundle>/lint-report-<date>.md` (do **not** modify files; let the user decide).

See `references/workflow-lint.md`.

## Dream — read-only audit lens

`mneme dream` is a **read-only audit lens** over the bundle. It returns a candidate report (OKF hard-rule candidates, Mneme writer-rule candidates, navigation candidates) — never a similarity score, never a similarity threshold, never a write.

`dream` does not shell `git`, never modifies the bundle, and the CLI exposes no `--apply` flag. The write-side workflow (what to do with the report after the user explicitly approves it) lives in `references/workflow-dream.md`; the agent performs those writes with its own `Write` / `Edit` tools, never from the CLI. The contract is enforced by `tests/test_dream_readonly.py`.

See `references/workflow-dream.md` for the full write-side workflow.

## references (load on demand)

`references/workflow-ingest.md` · `references/workflow-query.md` · `references/workflow-lint.md` · `references/workflow-dream.md` · `references/type-vocab.md` · `references/wiki-structure.md` · `references/index-design.md`.

OKF spec: <https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md>.