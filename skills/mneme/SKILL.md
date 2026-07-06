---
name: mneme
description: "Maintain a local, OKF-conformant LLM knowledge wiki of research/learning notes. Use when the user wants to ingest a source into their wiki, query the wiki, lint it for OKF conformance, run a scheduled maintenance cycle (dream), or initialize a new wiki. Triggers: 'mneme', 'my wiki', 'ingest this', 'query my notes', 'lint the wiki', 'dream', 'knowledge base', '查 wiki', '摄入笔记', '知识库'."
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

You drive all mneme operations through native tools (Read/Write/Edit/Bash/Glob/Grep) plus a thin CLI (`mneme init` / `mneme reindex`). **Never** call any independent agent SDK or `@tool` framework — your native tools ARE the agent runtime.

mneme keeps an external OKF v0.1 wiki of research/learning notes. The skill has 6 scenarios; pick the one matching the user's intent.

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

## Scenario: ingest <source path>

Distill a source (paper/article/note) into OKF concept pages:

1. `Read <source path>` to get the full text.
2. Decide how to decompose into concept pages (one page per atomic idea; one source may yield 1–15 pages).
3. For each page:
   - `Write <bundle>/concepts/<slug>.md` with frontmatter (`type`/`title`/`description`/`tags`/`timestamp`/`resource`) + body.
   - Cross-link related pages with absolute bundle-relative paths (`/concepts/other.md`).
4. `Edit <bundle>/index.md` — find or create the section heading: if `## <section>` (e.g. `## Concepts`, `## References`, `## Summaries`) already exists, append `* [Title](path) - description` under it; otherwise append a new `## <section>` heading followed by the entry. Use the page's frontmatter `type` to pick the section.
5. `Edit <bundle>/log.md` — append `## YYYY-MM-DD ingest | <source title>` + one-line note.
6. `Bash: python3 skills/mneme/scripts/mneme.py reindex` (or directly `python3 -c "import sys,indexlib; sys.path.insert(0,'skills/mneme/scripts'); ...; indexlib.reindex_bundle(bundle, indexlib.default_embed_fn())"`).
7. **Fallback:** if `fastembed` cannot download the model, retry with the **fake embed_fn** pattern from `tests/test_indexlib.py` (hash-based, no model). Only acceptable for tests — surface to the user that production reindex needs `pip install 'mneme[index]'`.

See `references/workflow-ingest.md` for the detailed checklist.

## Scenario: query <question>

Naive RAG: embed → KNN → top-k → read pages → synthesize answer with citations:

1. `Bash: python3 -c "import sys; sys.path.insert(0,'skills/mneme/scripts'); import indexlib; c = indexlib.open_index('<bundle>/.mneme/index.db'); print(indexlib.search(c, '<question>', k=10, embed_fn=indexlib.default_embed_fn()))"`
2. For each top chunk, `Read <bundle>/<chunk.path>` (use `concept_id` from the search result to derive path: `concepts/foo` → `concepts/foo.md`).
3. Synthesize an answer with **inline citations** as bundle-relative markdown links: `[/concepts/foo.md]([/concepts/foo.md)`.
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

## Scenario: dream (scheduled, fully automatic)

Auto-curate + maintain quality. **No user interaction** — this is a scheduled task.

**Pre-guard:**
1. `Bash: git rev-parse --git-dir 2>/dev/null || echo NOGIT`. If not a git repo, log a warning and skip git ops (still run curation + report).
2. If git: `Bash: git add -A && git commit -m "pre-dream $(date +%Y-%m-%dT%H:%M)" --allow-empty` (capture the commit SHA into a variable for the report).
3. Resolve the bundle (Step 0).

**Core loop (cap: `MNEME_MAX_DREAM_CHANGES_PER_RUN` env var, default 20 — soft cap, the host agent decides):**

| Action | Implementation |
|---|---|
| Merge duplicates | `Bash: python3 -c "import sys; sys.path.insert(0,'skills/mneme/scripts'); ..."` calling `indexlib.search(... k=20)` then grouping pairs with cosine distance ≤ 0.08 (i.e. similarity ≥ 0.92). Pick the merge target per pair. |
| Archive orphans | Call `okflib.find_orphans`. For each orphan with `timestamp` ≥ 90 days ago and zero log references: move to `archive/YYYY/`. |
| Add cross-links | For each orphan or low-link page, find the most-similar linked page via `indexlib.search`; add `[/concepts/X.md](/concepts/X.md)` to its body. |
| Build Summary | For each topic with ≥ 5 concepts, `Write` a new `<bundle>/summaries/<topic>.md` (type: Summary) with synthesized overview + links. |
| Reindex | `Bash: python3 skills/mneme/scripts/mneme.py reindex` (after all writes). |

**Atomic write protocol:** write every new/modified file to `<bundle>/.mneme/dream-pending/` first, then `Bash: cp` (or `git mv`) into place. If anything fails, the pending dir is the audit trail; the bundle stays unchanged.

**Post-guard:**
1. `Bash: python3 skills/mneme/scripts/validate_okf.py <bundle>` — must be 0 ERROR. If ERRORs, abort the commit and write a critical section to the report.
2. `Bash: git add -A && git commit -m "dream: $(date +%Y-%m-%d) [skip ci]" --author="mneme dream <dream@localhost>"` — commit the changes.
3. Capture the new commit SHA.
4. **Optional branch suggestion:** if the user has configured a base branch (e.g. via `MNEME_DREAM_BRANCH` env var), check it out from the dream commit and push: `git checkout -b dream/$(date +%Y-%m-%d) HEAD` — the user reviews and merges manually. This is suggested by the spec (§6.2) but not required.

**Report:** `Write <bundle>/dream-report-<date>.md`:

```markdown
# dream report — YYYY-MM-DD

## Summary
- Changes: N (cap was 20)
- pre-dream SHA: <sha>
- post-dream SHA: <sha>

## Changes
1. [merge] concepts/foo.md + concepts/bar.md → concepts/foo.md (similarity 0.94)
2. [archive] concepts/old.md → archive/2025/old.md (timestamp 245d, no log refs)
3. [link] concepts/x.md ↔ concepts/y.md
4. ...

## Validation
- validate: 0 ERROR / N WARN
- reindex: <bundle>/.mneme/index.db (M concepts)

## Revert
git revert <post-dream-SHA>
```

**If git is unavailable:** skip the commit step; the report still gets written; warn the user that there's no easy rollback.

## references (load on demand)

`scripts/validate_okf.py` (validator) · `references/workflow-ingest.md` · `references/workflow-query.md` · `references/workflow-lint.md` · `references/type-vocab.md` · `references/wiki-structure.md` · `references/index-design.md`.

OKF spec: <https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md>.
