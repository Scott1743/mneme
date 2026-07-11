---
type: Reference
title: mneme lint workflow (host-agent)
description: Detailed checklist for the lint scenario in SKILL.md.
---
# lint workflow (host-agent)

The lint scenario in SKILL.md curates without auto-modifying. This doc is the detailed checklist.

1. **Validate**: `Bash: python3 skills/mneme/scripts/validate_okf.py <bundle>` — must be 0 ERROR.
2. **Find orphans**: `Bash: python3 -c "import sys; sys.path.insert(0,'skills/mneme/scripts'); import okflib; print(okflib.find_orphans('<bundle>'))"`.
3. **Sample review**: read a handful of pages; look for:
   - Stale `timestamp` with no log reference
   - Contradictions between related pages
   - Missing cross-links between topics that share concepts
   - Pages that drifted into `archive/` candidates
4. **Write** the curated report to `<bundle>/lint-report-<date>.md` — **do not** modify the wiki files.

If the user approves follow-up changes, run them as `ingest` (for additions) or via explicit `Write`/`Edit` (for curations), not via lint.
