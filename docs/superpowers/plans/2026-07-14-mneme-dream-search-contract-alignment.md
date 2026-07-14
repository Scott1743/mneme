# Mneme dream/search Contract Alignment Plan

> Date: 2026-07-14
> Targets: 2.2.0 and 3.2.0
> Status: implementation in progress

## Goal

Finish the incomplete two-intent migration in both release lines:

- `dream` is the host-agent write workflow: read and audit, preview a concrete
  change set, wait for explicit approval, then write and validate.
- `search` is the host-agent read workflow: retrieve candidates, read complete
  authoritative Markdown pages, synthesize, and cite bundle paths.

The deterministic CLI is internal infrastructure:
`init / lint / reindex / search / dream / convert`. CLI dream is read-only,
CLI search returns candidates only, and convert invokes only a compatible
converter already installed by the user.

## Reference Contract

| Legacy file | Final file | Load condition |
|---|---|---|
| `workflow-ingest.md` | merged into `workflow-dream.md` | after approval; mandatory for complex writes |
| `workflow-query.md` | `workflow-search.md` | multi-page, cited, ambiguous, or semantic search |
| `workflow-dream.md` | approved write procedure | after approval and before writing |
| `workflow-lint.md` | read-only health review | explicit health check or failed validation |
| `index-design.md` | version-specific index details | troubleshooting or explicit L2 use |

The main skill exposes exactly `Scenario: dream` and `Scenario: search` and
states these conditions instead of merely listing reference filenames.

## Version Rules

### 2.2.0

- Standard-library SQLite FTS5 only.
- No semantic/model/dependency-install surface.
- Includes the local converter adapter without installing converters.

### 3.2.0

- FTS5 remains the default.
- `--l2` remains explicit opt-in, user-installed, and non-fallback.
- L2 changes candidate retrieval only; Markdown remains authoritative.
- Includes the same converter adapter and the existing read-only dream
  scheduler-snippet feature.

## Release Gates

1. Skill scenarios equal exactly `{"dream", "search"}`.
2. CLI commands equal exactly
   `{"init", "lint", "reindex", "search", "dream", "convert"}`.
3. Dream approval precedes every bundle write, including source copying.
4. Approved dream writes update `index.md` and prepend a `dream` log entry.
5. Search reads full pages, cites bundle paths, and never writes.
6. Legacy workflow files are absent from the release archive.
7. v2 contains no L2 path; v3 keeps default FTS5 and explicit `--l2`.
8. Existing `v2.0.0` and `v3.0.0` tags remain immutable.

## Execution

- [x] Implement, test, build, and commit 2.2.0 on `codex/v2.2.0`.
- [x] Implement the shared contract and v3-specific L2 rules on
      `codex/v3.2.0`.
- [x] Run the complete v3 test suite and inspect `mneme-3.2.0.zip`.
- [ ] Commit and push both release branches.
- [ ] Create and push `v2.2.0` and `v3.2.0` tags.
- [ ] Publish both GitHub releases with their matching zip assets.
- [ ] Only after the 2.2.0 asset exists, update source and packaged `SKILL.md`
      in the sibling project `森林密语` from the pinned 2.0.1/2.0.0 URL to
      `https://github.com/Scott1743/mneme/releases/download/v2.2.0/mneme-2.2.0.zip`.
- [ ] Verify, commit, and push the downstream project without overwriting its
      pre-existing worktree changes.
