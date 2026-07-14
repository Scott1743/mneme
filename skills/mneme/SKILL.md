---
name: mneme
version: 2.2.0
description: "Maintain and search a local, agent-curated OKF v0.1 Markdown wiki. Use when the user wants to dream (capture or curate knowledge) or search (recall and synthesize it). Triggers: 'mneme', 'my wiki', 'remember this', 'dream about X', 'search my wiki', '查 wiki', '搜索知识库', '梦', '记住这个'. v2.2 uses SQLite FTS5 and a read-only `mneme dream` audit CLI."
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
`search`, and `convert` are internal CLI operations used by those workflows.

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
4. Read relevant existing pages and prepare a concrete change preview: raw
   source destination, pages to add or edit, frontmatter/tags, links, and the
   planned `index.md` and `log.md` updates.
5. Show the audit and proposed change set. Require explicit user approval
   before every bundle write, including copying the raw source into `sources/`.

Only after approval and before writing, load `references/workflow-dream.md`.
It is
mandatory for a first dream, more than five proposed pages, edits to existing
concept pages, conflicts, merges, or archive proposals. Apply only the approved
scope. If the scope must materially expand, preview the expansion and ask
again.

Never automatically stage, commit, push, merge, archive, or delete knowledge.
Never make those decisions from a text or vector score.

## Scenario: search <question>

`search` is the read-side host-agent workflow. The CLI returns navigation
candidates only; the agent produces the answer.

1. Read the root `index.md` first and expand through titles, tags, links, and
   local text matches.
2. When ranked candidates are useful, run
   `python3 ~/.claude/skills/mneme/scripts/mneme.py search "<question>" --json -k 10`.
   Pass the question as an argument, never as generated Python source.
3. Always read each relevant Markdown page in full. Snippets and the derived SQLite
   index are never authoritative.
4. Synthesize the answer with inline bundle-relative citations such as
   `[Example](/concepts/example.md)`.
5. State coverage gaps honestly. If a reusable answer should be retained,
   offer a separate `dream`; `search` itself never writes.

Load `references/workflow-search.md` only for multi-page synthesis, multiple
plausible candidates, cited answers, or uncertainty about retrieval and
authority. A simple known-path or exact-title lookup does not require it.

## Internal maintenance commands

- `init <path>` scaffolds an OKF bundle and records its location.
- `lint [--bundle <path>]` validates and diagnoses without changing pages.
- `reindex [--bundle <path>]` atomically rebuilds the disposable FTS5 index.
- `dream [--bundle <path>] --json` audits without writing.
- `search <query> [--bundle <path>] --json` returns ranked candidates.
- `convert <source> --output <path>` creates derived readable text with an
  already-installed compatible converter; it never installs software and
  refuses overwrite unless the user explicitly requests `--force`.

Load `references/workflow-lint.md` only for an explicit wiki health check or
when post-dream validation fails. Load `references/index-design.md` only for
index troubleshooting. Load `references/wiki-structure.md` for structural
changes or a growing bundle. Load `references/type-vocab.md` only when a page
type is unknown or disputed.

## References

- `references/workflow-dream.md` - approved write-side procedure; load only
  after approval and before writing.
- `references/workflow-search.md` - full-page synthesis and citation procedure;
  load only under the search conditions above.
- `references/workflow-lint.md` - read-only health review and diagnostics.
- `references/type-vocab.md` - optional, non-registered type guidance.
- `references/wiki-structure.md` - growing-bundle organization.
- `references/index-design.md` - disposable FTS5 implementation details.

OKF specification: <https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md>.
