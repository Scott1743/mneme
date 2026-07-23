---
name: mneme
version: 4.8.0
description: "Maintain and search a local, agent-curated OKF v0.1 Markdown wiki, including a disposable SQLite knowledge graph, agent-extracted graph enrichment via graph ingest, hybrid Graph + FTS5 + explicitly activated L2 retrieval, and optional nightly 02:00 agent health tasks in report-only or guarded auto-repair mode. Use when the user wants to dream (capture or curate knowledge), search (recall and synthesize it), initialize a wiki, rebuild graph navigation, or schedule wiki health maintenance. Triggers: 'mneme', 'my wiki', 'remember this', 'dream about X', 'search my wiki', 'nightly wiki health', '查 wiki', '搜索知识库', '梦', '记住这个'. v4 keeps Markdown authoritative, derives graph.db from pages/tags/links, keeps FTS5 zero-dependency, and adds semantic candidates to hybrid only after explicit L2 activation."
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
  - AskUserQuestion
---

# mneme - lightweight LLM wiki

Use native tools plus the deterministic CLI shipped with this skill. Never
call an independent agent SDK or tool framework: native tools are the agent
runtime, and the OKF Markdown bundle is the source of truth.

```bash
python3 ~/.claude/skills/mneme/scripts/mneme.py <subcmd> [args]
```

The user surface has exactly two intents: `dream` writes after preview and
approval; `search` reads and answers. `init`, `lint`, `reindex`, `dream`,
`search`, `convert`, and `serve` are internal CLI operations used by those
workflows.

## Resolve the bundle once per task

Use the first available location:

1. An explicit bundle path supplied by the user.
2. `$MNEME_BUNDLE`.
3. `$HOME/.config/mneme/config.toml` key `bundle_path`.
4. Walk up from cwd for a root `index.md` with `okf_version` frontmatter.
5. `./wiki` when it exists.
6. Otherwise ask for a path or offer the internal `init` command.

Reuse the resolved path for the current task. Resolve again if the user selects
another bundle or the relevant environment/configuration changes. Do not rely
on persistent agent memory for bundle selection.

## OKF v0.1 write contract

1. Every non-reserved `.md` file MUST have parseable YAML frontmatter.
2. Every such frontmatter MUST contain a non-empty `type`.
3. Reserved `index.md` and `log.md` MUST follow their OKF structures.
4. Every Mneme-written concept page has at least one `tags` value.
5. Use absolute bundle-relative links such as `/concepts/example.md`.

Unknown `type` values, extra frontmatter keys, missing optional fields, broken
links, and a missing index are tolerated by consumers. Report them when useful;
never reject the rest of the bundle because of them.

## Scenario: dream [source or curation request]

`dream` is the write-side host-agent workflow. The `mneme dream` CLI is only a
read-only audit step and has no apply mode.

Before approval:

1. Resolve the bundle. If it does not exist, preview the proposed location and
   use `init` only after the user agrees to create it.
2. Read the supplied source without copying or modifying the bundle. When a
   local PDF, DOCX, or PPTX is unreadable, offer a preview-only conversion to
   an explicit temporary output path with `mneme convert`; it only uses a
   compatible converter already installed by the user.
3. Run `python3 ~/.claude/skills/mneme/scripts/mneme.py dream --bundle <bundle> --json`
   to audit the current bundle without writing.
   Read `tag_health` and `enrichment_health` as advisory curation signals, not
   OKF errors.
4. Read relevant existing pages and prepare a concrete change preview: the
   immutable artifact destination under `raw-sources/`, the OKF `Source` page
   under `sources/`, other pages to add or edit, frontmatter/tags, links, and
   the planned `index.md` and `log.md` updates. A raw filename ending in `.md`
   is stored with `.raw` appended (for example `paper.md.raw`) so OKF does not
   mistake the immutable artifact for a concept document.
5. Show the audit and proposed change set. Require explicit user approval
   before every bundle write, including preserving the raw artifact and
   creating its `Source` page.
   This per-run approval rule governs interactive dreams; the only exception is
   the bounded standing approval for a user-selected guarded nightly task below.

Only after approval and before writing, load `references/workflow-dream.md`.
It is mandatory for a first dream, more than five proposed pages, edits to
existing concept pages, conflicts, merges, or archive proposals. Apply only the
approved scope. If the scope must materially expand, preview it and ask again.

While preparing any preview that adds or changes tags, entities, or semantic
relations, load `references/tag-graph-curation.md` before proposing those
fields. Reuse the bundle's vocabulary and keep metadata sparse; explain any
intentional exception to its advisory budgets in the preview.

Never automatically stage, commit, push, merge, archive, or delete knowledge.
Never make those decisions from a text or vector score.

### Enrich the graph after approved writes

After approved page writes and `reindex --graph`, you may enrich the derived
graph with entities and relations you extract from the new or changed pages.
The CLI never calls an LLM: you are the extractor, `mneme graph ingest` is the
deterministic writer, and Markdown stays authoritative. Show the extraction
JSON in the change preview and ingest only after the same approval that covers
the writes. Payload contract (tolerant consumer; bad blocks are skipped with
warnings):

```json
{"version": 1, "pages": [{"page": "concepts/example.md",
  "entities": [{"name": "...", "type": "concept", "description": "...", "confidence": 0.9}],
  "relations": [{"subject": "...", "predicate": "...", "object": "...", "evidence": "...", "confidence": 0.8}]}]}
```

Keep entities faithful to page text, reuse existing entity names across pages
so the graph connects, and prefer a few high-confidence relations over
exhaustive weak ones. Ingest with
`python3 ~/.claude/skills/mneme/scripts/mneme.py graph ingest <extraction.json> --bundle <bundle>`;
re-ingesting a page replaces only that page's prior extracted relations.
The CLI records approved extraction blocks in
`<bundle>/.mneme/graph-extractions.json` and replays them during later Graph
rebuilds, so `reindex --graph` does not silently discard enrichment. This
manifest is derived navigation data, never an authority over Markdown.

### Offer a nightly health task

When the user directly requests scheduled wiki maintenance, follow this section
immediately. Otherwise, after `init` or the first successful interactive
`dream` for a bundle, use the host's recurring-task capability, when available,
to check whether that bundle already has a nightly Mneme task. If none exists,
offer once to create a daily 02:00 local-time task and ask the user to choose
one mode:

- **Report only**: the scheduled agent audits, lints, reads relevant pages, and
  reports findings without changing the bundle.
- **Guarded auto-repair**: the scheduled agent may apply only the bounded,
  non-destructive health fixes in `references/workflow-nightly-dream.md`, then
  validates and reports the exact diff. The user's explicit mode selection is
  standing approval only for that narrow repair scope.

Do not create or change a recurring task until the user explicitly chooses a
mode. Respect a prior decline and do not repeatedly prompt. Load
`references/workflow-nightly-dream.md` before composing either scheduled task.
Use a host-agent recurring task, not `mneme dream --schedule`: that CLI flag is
an agentless, report-only scheduler-snippet fallback and cannot perform repair.

## Scenario: search <question>

`search` is the read-side host-agent workflow. The CLI returns navigation
candidates only; the agent produces the answer.

1. Read the root `index.md` first and expand through titles, tags, links, and
   local text matches.
2. When ranked candidates are useful, run:
   `python3 ~/.claude/skills/mneme/scripts/mneme.py search "<question>" --json -k 10`.
   A bundle with a fresh `<bundle>/.mneme/graph.db` uses hybrid Graph + FTS5
   retrieval automatically. After L2 is explicitly activated, bare search uses
   full Hybrid: Graph + global FTS5 + L2 semantic candidates. Graph never hides
   lexical or semantic matches. A stale Graph is ignored while the other active
   legs continue.
3. Use `search --mode graph|fts|hybrid|l2` only when diagnosing or explicitly
   comparing retrieval paths. Hybrid uses L2 only when it is the persisted
   active mode; `--mode l2` isolates semantic retrieval for diagnostics. If
   Graph has no entity match, the other active legs still return candidates.
4. When the user explicitly requests semantic recall, load
   `references/index-design.md`. After the user installs the optional
   dependencies, run `reindex --l2` once to build and activate L2. Later plain
   `search` commands automatically add L2 to Hybrid; never add `--l2` to each
   search, install dependencies, download a model, or switch modes on the
   user's behalf. L2 failures never silently fall back to Graph or FTS5.
5. Always read each relevant Markdown page in full. Snippets, chunks, distances,
   graph edges, and derived SQLite indexes are never authoritative.
6. Synthesize the answer with inline bundle-relative citations such as
   `[Example](/concepts/example.md)`.
7. State coverage gaps honestly. If a reusable answer should be retained,
   offer a separate `dream`; `search` itself never writes.

Load `references/workflow-search.md` only for multi-page synthesis, multiple
plausible candidates, cited answers, semantic recall, or uncertainty about
retrieval and authority. A simple known-path or exact-title lookup does not
require it.

## Optional visual panel (`mneme serve`)

Proactively mention the local web console when it helps the user:

- after `init` completes,
- after every approved dream write finishes,
- when the user asks about wiki health or wants to browse the wiki.

Tell them they can run
`python3 ~/.claude/skills/mneme/scripts/mneme.py serve --open`
(or the equivalent entry point) to start a localhost-only visual panel with
overview, search, browse, lint, dream-audit, and Graph tabs. The Graph
workbench exposes separate page/tag/link and approved agent-enrichment slices,
including relation evidence and links back to authoritative Markdown pages.
Its reindex action always refreshes FTS5 and Graph; when L2 is the persisted
mode it rebuilds L2 first and reports any failure without silently falling
back. It never invents agent enrichment. It binds 127.0.0.1 by default, prints
a per-process session token at startup, stops with Ctrl-C, and never writes
factual Markdown. Do not start or keep the server running on the user's behalf
unless the user explicitly asks; just offer the command.

## Internal maintenance commands

- `init <path>` scaffolds an OKF bundle and records its location.
- `lint [--bundle <path>]` validates and diagnoses without changing pages.
- `reindex [--bundle <path>] [--graph | --l2 | --fts5]` atomically rebuilds
  disposable indexes. `--graph` derives `<bundle>/.mneme/graph.db` from OKF
  pages/tags/links and refreshes FTS5 without changing Markdown. `--l2`
  explicitly builds and persists semantic mode; `--fts5` explicitly switches
  back. Bare `reindex` uses the persisted FTS5/L2 mode.
- `dream [--bundle <path>] --json` audits without writing, reports advisory
  tag/enrichment vocabulary health, and includes Graph health counters when
  `graph.db` exists. Its optional schedule flags print
  agentless, report-only scheduler snippets and never install them; the default
  fallback time is 02:00 local time.
- `search <query> [--bundle <path>] [--mode graph|fts|hybrid|l2] --json` returns
  candidates. Hybrid is Graph + FTS5 by default and adds semantic candidates
  when L2 is active; explicit modes isolate a retrieval path for diagnostics.
- `graph ingest <extraction.json> [--bundle <path>]` merges agent-extracted
  entities/relations into `<bundle>/.mneme/graph.db` (schema v3). Use `"-"` as
  the file to read JSON from stdin. Requires an existing graph index; the
  payload contract is in the dream section above.
- `convert <source> --output <path>` creates derived readable text with an
  already-installed compatible converter; it never installs software and
  refuses overwrite unless the user explicitly requests `--force`.
- `serve [--bundle <path>] [--host 127.0.0.1] [--port 8620] [--open]` starts
  the foreground localhost web console (read-only + mode-aware disposable
  L2/FTS5/Graph reindex; Ctrl-C stops). It prints a session token; a bundle without
  `index.md` opens on the empty-bundle guide page.

Load `references/workflow-lint.md` only for an explicit wiki health check or
when post-dream validation fails. Load `references/index-design.md` only for
index-mode selection or troubleshooting. Load `references/wiki-structure.md`
for structural changes or a growing bundle. Load `references/type-vocab.md`
only when a page type is unknown or disputed.

## References

- `references/workflow-dream.md` - approved write-side procedure; load only
  after approval and before writing.
- `references/tag-graph-curation.md` - bundle-local tag vocabulary and sparse
  graph enrichment guidance; load while preparing previews that change either.
- `references/workflow-nightly-dream.md` - recurring 02:00 agent task modes,
  standing-approval boundary, guarded repairs, and report format.
- `references/workflow-search.md` - full-page synthesis and citation procedure;
  load only under the search conditions above.
- `references/workflow-lint.md` - read-only health review and diagnostics.
- `references/type-vocab.md` - optional, non-registered type guidance.
- `references/wiki-structure.md` - growing-bundle organization.
- `references/index-design.md` - v4 Graph + FTS5 hybrid retrieval and explicit opt-in L2 details.

OKF specification: <https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md>.
