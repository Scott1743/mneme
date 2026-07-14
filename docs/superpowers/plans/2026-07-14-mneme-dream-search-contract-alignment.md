# Mneme dream/search Contract Alignment Plan

> Date: 2026-07-14
> Status: planned, not implemented
> Targets: 2.2.0 and 3.2.0 feature releases

## Goal

Finish the incomplete v2 contract migration and carry the same correction into
v3 without losing v3's opt-in semantic search. The user-facing skill has only
two intents:

- `dream`: the host-agent write workflow. It previews proposed changes, waits
  for explicit user approval, then writes with native `Write` / `Edit` tools.
- `search`: the host-agent read workflow. It finds candidates, reads the full
  authoritative Markdown pages, and synthesizes an answer with bundle-relative
  citations.

The CLI remains deterministic infrastructure:
`init / lint / reindex / search / dream / convert`. CLI `dream` is read-only;
CLI `search` returns candidates only, and `convert` only invokes a compatible
converter already installed by the user.

## Current Drift To Correct

Both v2.0.0 and v3.0.0 still expose seven skill scenarios, including legacy
`ingest` and `query`. This contradicts `AGENTS.md`, `README.md`, and the 2.0
changelog. In particular:

- legacy `ingest` writes before a dream preview and user approval;
- the skill-level `search` stops at snippets instead of answering from full
  pages;
- `workflow-ingest.md` and `workflow-query.md` preserve the old taxonomy;
- reference links say "load on demand" but do not define load conditions;
- migration tests allow extra scenarios instead of enforcing exactly
  `dream/search`;
- v2 contains stale L2/model-load language;
- v3 inherits the same workflow drift and also has inconsistent `--l2`
  instructions and stale v2/v2.1 prose.

## Frozen Responsibility Split

| Layer | `dream` | `search` |
|---|---|---|
| User intent | Capture/curate knowledge | Ask the wiki |
| Host agent | Preview, request approval, write, validate | Retrieve, read full pages, synthesize, cite |
| CLI | Read-only audit report | Ranked candidates/snippets only |
| Authority | OKF Markdown bundle | OKF Markdown bundle |

`init`, `lint`, and `reindex` are internal maintenance operations, not
additional user scenarios.

## Target Skill Shape

`skills/mneme/SKILL.md` will contain:

1. compact installation and CLI invocation notes;
2. bundle resolution, performed once per task and reused unless the user or
   environment selects another bundle;
3. OKF hard rules and Mneme writer rules;
4. exactly `## Scenario: dream` and `## Scenario: search`;
5. a compact internal CLI reference for `init/lint/reindex`;
6. explicit conditional-loading rules for every reference.

It will not contain `Scenario: ingest`, `Scenario: query`, or `Scenario: lint`.

## Dream Workflow

### Before approval (kept in `SKILL.md`)

1. Resolve the bundle; offer internal `init` when none exists.
2. Read the supplied source without copying or modifying the bundle.
3. Run `mneme dream --bundle <bundle> --json` as a read-only preflight audit.
4. Inspect relevant existing pages and prepare a proposed change set:
   source destination, pages to add/update, frontmatter/tags, links, and
   `index.md` / `log.md` changes.
5. Show the audit plus proposed change set to the user.
6. Require explicit approval before any bundle write, including copying the raw
   source into `sources/`.

The CLI audit describes the current bundle; the host agent's proposed change
set previews the new source. Neither is a write operation.

### After approval (`references/workflow-dream.md`)

1. Copy the raw source unchanged, refusing conflicting overwrites.
2. Write or edit atomic concept pages with `type`, at least one `tag`, and
   bundle-relative links.
3. Update `index.md` and prepend `## YYYY-MM-DD dream | <title>` to `log.md`.
4. Run `lint`, then `reindex`, then the read-only dream audit again.
5. Report validation and remaining candidates; never stage, commit, or push.
6. Ask for new approval only if the approved scope must materially expand.

Load `workflow-dream.md` only after approval and before writing. It is mandatory
for a first dream, an operation expected to create more than five pages, any
edit to existing concept pages, conflicts, merges, or archive proposals.

## Search Workflow

1. Resolve the bundle once.
2. Read the root `index.md`; expand through titles, tags, links, and local text
   matching.
3. Use `mneme search --json` when candidate ranking is useful.
4. Read the complete authoritative Markdown pages for relevant candidates.
5. Synthesize an answer with inline bundle-relative citations.
6. State coverage gaps honestly. Offer a separate `dream` for useful backfill;
   `search` itself never writes.

Rename `workflow-query.md` to `workflow-search.md`. Load it only when search
requires multi-page synthesis, CLI returns several plausible candidates, the
answer needs citations, or the agent is uncertain about retrieval/authority
rules. A simple path/title lookup can stay in the main scenario.

## Reference Restructure

| Current | Target | Conditional load |
|---|---|---|
| `workflow-ingest.md` | Merge into `workflow-dream.md`, then remove | After approval; mandatory for complex writes |
| `workflow-query.md` | Rename/rewrite as `workflow-search.md` | Multi-page/cited/ambiguous search |
| `workflow-dream.md` | Rewrite as approved write-side procedure | After approval only |
| `workflow-lint.md` | Keep or rename to `workflow-maintenance.md` | Explicit health check or failed post-write validation |
| `type-vocab.md` | Keep | Unknown or disputed page type |
| `wiki-structure.md` | Keep and remove stale index-tier claims | Structural changes or growing bundle |
| `index-design.md` | Version-specific | Index troubleshooting; v3 L2 details only on explicit L2 use |

The bottom of `SKILL.md` must state these conditions, not merely list filenames.

## Version-Specific Rules

### v2.2.0

- FTS5 is the only index implementation.
- Remove all L2, model-load, embedding, dependency-install, and `--l2` text.
- `reindex` and `search` remain standard-library-only.

### v3.2.0

- Preserve FTS5 as the default.
- Preserve `--l2` as explicit opt-in only; never auto-install dependencies or
  silently switch index modes.
- `workflow-search.md` must distinguish default FTS5 commands from commands
  explicitly carrying `--l2`.
- `index-design.md` must describe both default FTS5 and optional L2 accurately.
- Move detailed dependency/model instructions out of the main skill and load
  them only when the user explicitly requests semantic search.
- Remove stale claims that L2 is deferred to v2.1 or absent from the release.

L2 changes candidate retrieval only. It does not change the dream approval
contract or the requirement to read full Markdown pages before answering.

## Implementation Order

- [x] 1. Add strict failing contract tests on the 2.x maintenance branch.
- [x] 2. Rewrite `SKILL.md` around exactly two scenarios.
- [x] 3. Merge ingest into dream; rename query to search; add conditional loads.
- [x] 4. Align remaining references and all dream log prefixes.
- [x] 5. Remove v2-only stale L2 language and run focused tests.
- [x] 6. Run the complete v2 test suite and build/inspect the skill zip.
- [ ] 7. Port the contract/refactor commits to the v3 maintenance branch.
- [ ] 8. Reintroduce only the version-specific optional L2 instructions.
- [ ] 9. Fix v3 `AGENTS.md`, references, changelog, and L2 tests.
- [ ] 10. Run the complete v3 test suite and build/inspect the skill zip.
- [ ] 11. Release immutable versions `2.2.0` and `3.2.0`; do not rewrite
      existing `v2.0.0` or `v3.0.0` tags.
- [ ] 12. After both Mneme branches, tags, and GitHub release assets are
      published, update both source and packaged `SKILL.md` files in the
      sibling project `森林密语`: replace its pinned Mneme 2.0.1 release URL
      with the final Mneme 2.2.0 release URL, verify the reference, and commit
      and push that project without changing unrelated files.

## Required Test Gates

1. Skill scenario headings equal exactly `{"dream", "search"}`.
2. CLI commands equal exactly
   `{"init", "lint", "reindex", "search", "dream", "convert"}`.
3. `Scenario: ingest` and `Scenario: query` are absent from the release zip.
4. Dream audit is byte-for-byte read-only and exposes no apply flag.
5. Skill text requires approval before every bundle write.
6. Dream writes update both `index.md` and newest-first `log.md` with a
   `dream` prefix.
7. Search reads full pages and synthesizes citations; snippets remain
   navigation aids.
8. Search never writes; useful backfill is offered as a separate dream.
9. Every named reference exists in the release artifact, and removed legacy
   references are not mentioned.
10. v2 contains no L2 surface. v3 default remains FTS5 and `--l2` remains
    explicit, user-installed, and non-fallback.
11. OKF tolerance remains unchanged: unknown types/keys, optional-field gaps,
    broken links, and missing indexes do not invalidate other pages.

## Documentation And Release Checks

- Align `AGENTS.md`, `CLAUDE.md`, `README.md`, `CHANGELOG.md`, introduction,
  skill, and references with the same two-intent vocabulary.
- Remove the nonexistent `SKILL cn.md` tree entry unless the file is restored
  intentionally.
- Update release-layout tests for renamed/removed references.
- Keep existing release tags immutable; document fixes in new 2.2.0 and 3.2.0
  changelog entries.
- Treat the `森林密语` URL update as a downstream release dependency: do not
  point it at 2.2.0 until the 2.2.0 GitHub release asset actually exists.

## Non-Goals

- No change to OKF v0.1 MUSTs or tolerance behavior.
- No automatic content merge/archive decision based on FTS or vector scores.
- No new service, SDK, MCP server, or persistent agent memory.
- No automatic dependency installation, git staging, commit, or push.
