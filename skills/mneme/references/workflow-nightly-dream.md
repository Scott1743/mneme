---
type: Reference
title: mneme nightly dream workflow
description: Run a recurring 02:00 agent health check in report-only or guarded auto-repair mode.
---

# nightly dream workflow

This workflow is for a recurring host-agent task, not an agentless OS job. Pin
the resolved bundle path and the user-selected mode in the task. Schedule it
for 02:00 in the user's local timezone unless the user chooses another time.

Create the task with a recognizable title such as
`Mneme nightly health - <bundle-name>`. Its prompt must include the absolute
bundle path, selected mode, local timezone, and this execution contract:

```text
Run the Mneme nightly dream health workflow for <absolute-bundle-path> in
<report-only|guarded-auto-repair> mode. Load the installed mneme skill and its
references/workflow-nightly-dream.md instructions, follow the selected mode's
authorization boundary, validate the result, and report every finding, change,
skip, and failure to the user. Do not broaden the repair scope.
```

## Shared procedure

1. Read the root `index.md`, then run `mneme dream --bundle <bundle> --json`
   and `mneme lint --bundle <bundle>`.
2. Read every page implicated by a finding before classifying it. Audit output,
   lint output, indexes, and snippets are navigation aids rather than authority.
3. Report OKF errors separately from Mneme warnings and navigation concerns.
4. Never install dependencies, switch retrieval modes, or use network access.

## Report-only mode

Do not write anywhere in the bundle. Report the findings, affected paths,
recommended fixes, and whether the active disposable index appears stale.

## Guarded auto-repair mode

The user's explicit selection of this mode when creating or updating the task
is standing approval for the bounded fixes below. It is not approval for normal
knowledge curation.

Before editing, inspect the proposed paths for pre-existing user changes. Skip
any overlapping dirty path and report it. If more than five concept pages would
change, or any fix is ambiguous, stop and produce a report-only result.

Allowed fixes:

- repair required or recommended frontmatter only when the value is clear from
  the existing page; preserve every unknown key;
- add a missing Mneme tag only when the page states the topic explicitly;
- repair an internal link only when exactly one existing target is evident;
- synchronize `index.md` entries for pages changed in the same run;
- update timestamps only on pages changed in the same run;
- prepend one `## YYYY-MM-DD dream | nightly health` entry to `log.md` when a
  bundle write occurred;
- rebuild the already-selected disposable index after validation.

Never change factual body text or raw sources. Never create new knowledge pages,
overwrite sources, merge, archive, move, rename, or delete pages. Never run
`git add`, `git commit`, `git push`, or any other git command that changes state.
Contradictions, stale claims, ambiguous `type` values, and uncertain links are
report-only findings.

After editing, run lint and the read-only dream audit again. If validation
worsens, restore only this run's edits from the captured originals and report
the failure. The final report includes the selected mode, before/after counts,
every changed or skipped path, validation status, and a concise diff summary.
