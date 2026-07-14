---
type: Reference
title: mneme dream workflow (host-agent, write-side)
description: Write-side workflow for dream. The `mneme dream` CLI itself is read-only; this doc tells the agent how to apply approved changes.
---

# dream workflow (host-agent)

The `mneme dream` CLI is **read-only**. It surfaces a candidate audit report
(OKF hard-rule candidates, Mneme writer-rule candidates, navigation
candidates) for the agent to review.

After the user **explicitly approves** the report, the agent performs writes
using its own `Write` / `Edit` tools. This separation — audit in the CLI,
writes in the agent loop after approval — is the v2.0 contract enforced by
`tests/test_dream_readonly.py`. There is no `--apply` flag on the CLI by
design.

## What `mneme dream` reports

The report has four sections, all candidate-only (no similarity scores, no
thresholds, no auto-decisions):

- `okf_hard_rules` — OKF v0.1 §4 candidates (e.g. `OKF-NO-FRONTMATTER`).
- `mneme_writer_rules` — Mneme writer-rule candidates
  (e.g. `MNEME-TAG-MISSING` for Mneme-written concept pages).
- `navigation.dangling` / `orphan` / `tag_drift` — link and orphan candidates.
- `_meta.raw_distance_only = true` — the report never contains a
  similarity threshold. v2.1 will add raw distance candidates when L2 lands.

## Write-side rules (after user approval)

The agent must NEVER:

- shell `git add -A`, `git commit`, or `git push` automatically — the dream
  audit is **not** a commit trigger.
- merge or archive pages from an automated similarity threshold.
- skip `mneme lint` after writing.
- mutate the bundle based on `dream`'s audit alone — user approval is
  required for every change.

## Steps (after the user has approved the audit)

1. Read the `mneme dream` report; identify each candidate change.
2. Surface each candidate in the chat; require explicit user approval per
   change. Aggregate approval ("approve all") is acceptable when the user
   wants it.
3. Apply approved edits via `Write` / `Edit` to the bundle.
4. Update `wiki/index.md` (add the new page under the section matching its
   `type`) and `wiki/log.md` (prepend `## YYYY-MM-DD ingest | <title>`).
5. Run `mneme lint <bundle>` and `mneme reindex` to keep the bundle healthy.
6. Re-run `mneme dream` to confirm the audit is now clean.

## OKF contract reminders

- Every non-reserved `.md` MUST have YAML frontmatter with non-empty `type`.
- `index.md` / `log.md` are reserved; bundle-root `index.md` may carry
  `okf_version: 0.1`.
- Tolerance (SPEC §9): missing optional fields, unknown `type`, unknown
  frontmatter keys, dangling links, missing `index.md` — never reject the
  bundle.
- Mneme adds `tags` as a writer rule for Mneme-written pages, not an OKF
  MUST. External OKF bundles may have untagged pages; dream reports them
  as candidates only.
