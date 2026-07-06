---
name: mneme
description: "Maintain a local, OKF-conformant LLM knowledge wiki of research/learning notes. Use when the user wants to ingest a source (paper/article/note) into their wiki, query the wiki, lint/check OKF conformance, or initialize a new wiki. Triggers: 'mneme', 'my wiki', 'ingest this', 'query my notes', 'lint the wiki', 'knowledge base', '查 wiki', '摄入笔记', '知识库'."
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

mneme maintains an external OKF v0.1 wiki of research/learning notes. You are its disciplined maintainer (the schema layer). Three workflows: **ingest**, **query**, **lint** (+ **init**).

## Step 0: resolve the bundle (EVERY operation)

Find the wiki bundle in this order; use the first hit:
1. `~/.config/mneme/config.toml` key `bundle_path`.
2. `MNEME_BUNDLE` env var.
3. An explicit path the user gave in this request.
4. Auto-discover: walk up from cwd for a root `index.md` whose frontmatter contains `okf_version`.
5. `./wiki` if it exists.
6. None found → ask the user for the path, or offer `init`.

`config.toml` is simple `key = "value"` lines; parse with stdlib (no PyYAML needed).

## OKF v0.1 conformance (hard rules — never violate on write)

1. Every non-reserved `.md` MUST have a `---`-delimited YAML frontmatter block.
2. Every frontmatter MUST have a non-empty `type`.
3. Reserved `index.md` (directory listing; no frontmatter except root `okf_version`) and `log.md` (date-prefixed timeline) follow their structure.

Do NOT reject unknown `type` values, extra frontmatter keys, or broken links — warnings only.

## type vocab (recommended, non-registered)

`Concept` (idea/topic) · `Reference` (distilled external source) · `Summary` (synthesis) · `Source` (raw doc in sources/).

## ingest <source path>

1. Resolve bundle (Step 0). If absent and user wants, run `init`.
2. Read the source (.md/.txt only in v1). Copy to `sources/<slug>.md` (immutable raw layer).
3. Read the source; optionally discuss key points with the user.
4. Write concept page(s) under an appropriate subdir, each with frontmatter: `type`, `title`, `description`, `tags`, `timestamp` (ISO 8601), `resource` (source path).
5. Update related existing pages with cross-links (absolute bundle-relative: `/dir/concept.md`).
6. Update `index.md`: add `* [Title](path) - description` under the right section.
7. Append to `log.md`: `## YYYY-MM-DD ingest | <title>` + one-line note.
8. Run `python3 scripts/validate_okf.py <bundle>`. Fix any ERROR before ingest is done.

## query <question>

1. Resolve bundle.
2. Read `index.md` first (progressive disclosure) to locate relevant pages.
3. Read those pages.
4. Synthesize an answer WITH citations (bundle-relative links + external citations present).
5. If the answer is broadly useful and no page covers it, OFFER to backfill as a new concept page (do not auto-write in v1).

## lint

1. Resolve bundle.
2. Run `python3 scripts/validate_okf.py <bundle>`. Report ERRORs (must fix) and WARNings.
3. Curate warnings: contradictions, stale claims, orphan pages, missing cross-links, important concepts with no page. Propose fixes; apply only with user approval.

## init <path>

Scaffold a new empty bundle and record it:
- `<path>/index.md` with `okf_version: "0.1"` frontmatter + empty `# Concepts` body.
- `<path>/log.md` with `# Directory Update Log` header.
- `<path>/sources/.gitkeep`.
- Write `bundle_path = "<path>"` to `~/.config/mneme/config.toml` (create `~/.config/mneme/` if needed).

## references (load on demand)

`references/workflow-ingest.md` · `references/workflow-query.md` · `references/workflow-lint.md` · `references/type-vocab.md`. Validator: `scripts/validate_okf.py`. OKF spec: `.research/upstream/OKF-SPEC.md`.
