---
type: Reference
title: mneme lint workflow (host-agent)
description: Detailed checklist for the lint scenario in SKILL.md.
---
# lint workflow (host-agent)

The lint scenario in SKILL.md curates without auto-modifying. This doc is the detailed checklist.

1. **Validate**: `Bash: python3 ~/.claude/skills/mneme/scripts/mneme.py lint <bundle>` — must be 0 ERROR. The lint command runs OKF validation + `find_orphans` analysis in one call (since v0.6.0); orphan results print to stderr.
2. **Find orphans**: redundant with step 1 — `mneme lint` already calls `okflib.find_orphans()` internally. To call it directly without the OKF validation step, use `python3 ~/.claude/skills/mneme/scripts/mneme.py lint <bundle>` and read the `orphan concept pages` section of stderr.
3. **Sample review**: read a handful of pages; look for:
   - Stale `timestamp` with no log reference
   - Contradictions between related pages
   - Missing cross-links between topics that share concepts
   - Pages that drifted into `archive/` candidates
4. **Write** the curated report to `<bundle>/lint-report-<date>.md` — **do not** modify the wiki files.

If the user approves follow-up changes, run them as `ingest` (for additions) or via explicit `Write`/`Edit` (for curations), not via lint.
