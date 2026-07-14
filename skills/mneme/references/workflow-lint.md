---
type: Reference
title: mneme lint workflow (read-only health review)
description: Validate OKF rules and review navigation health without modifying the bundle.
---

# lint workflow

1. Run `python3 ~/.claude/skills/mneme/scripts/mneme.py lint --bundle <bundle>`.
   Distinguish OKF errors from warnings and navigation diagnostics.
2. Read a representative sample of related pages and review stale timestamps,
   contradictions, missing cross-links, or possible archive candidates.
3. Report findings in the conversation. Do not create a report file inside the
   bundle and do not modify concept pages.
4. If changes are warranted, propose them as a separate `dream`. That workflow
   supplies the preview, approval, write, log, validation, and reindex steps.

Unknown types or keys, optional-field gaps, broken links, and a missing index
do not make otherwise valid pages unusable.
