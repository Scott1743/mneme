---
type: Reference
title: mneme ingest workflow (host-agent)
description: Detailed checklist for the ingest scenario in SKILL.md.
---
# ingest workflow (host-agent)

The ingest scenario in SKILL.md guides the host agent through these steps. This doc is the detailed checklist — read it before doing a non-trivial ingest.

0. **Preserve the raw source.** Before reading for distillation, copy the original file unchanged into `<bundle>/sources/<basename>`. The OKF v0.1 source-of-truth contract requires the raw source to remain on disk alongside the distilled concept pages. If the destination already exists with different content, abort and ask the user — do not overwrite.
1. **Read** the source file end-to-end.
2. **Decompose** into concept pages:
   - One page per atomic idea (one source can yield 1–15 pages).
   - Choose `type` per page (Concept / Reference / Summary / Source).
   - Slug = lowercase, non-alnum→hyphen.
3. **Write** each page to `<bundle>/concepts/<slug>.md`:
   ```yaml
   ---
   type: Concept
   title: <display>
   description: <one-line>
   tags: [<t1>, <t2>]
   timestamp: <ISO 8601>
   resource: <source path>
   ---
   <body>
   ```
4. **Cross-link** related pages with `/concepts/<slug>.md`.
5. **Edit `<bundle>/index.md`** — add `* [Title](path) - description` under `# Concepts`.
6. **Edit `<bundle>/log.md>`** — **prepend** (insert at top) `## YYYY-MM-DD ingest | <source title>` + one-line note. The OKF v0.1 log contract requires newest-first.
7. **Reindex**: `Bash: python3 skills/mneme/scripts/mneme.py reindex`.
8. **Validate**: `Bash: python3 skills/mneme/scripts/validate_okf.py <bundle>` — must be 0 ERROR.

If `fastembed` model download fails, surface the error to the user and tell them to install `pip install 'mneme[index]'`. There is no production fallback — see `SKILL.md` ingest step 7.
