---
type: Reference
title: mneme ingest workflow (host-agent)
description: Detailed checklist for the ingest scenario in SKILL.md.
---
# ingest workflow (host-agent)

The ingest scenario in SKILL.md guides the host agent through these steps. This doc is the detailed checklist — read it before doing a non-trivial ingest.

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
6. **Edit `<bundle>/log.md`** — append `## YYYY-MM-DD ingest | <source title>` + one-line note.
7. **Reindex**: `Bash: python3 skills/mneme/scripts/mneme.py reindex`.
8. **Validate**: `Bash: python3 skills/mneme/scripts/validate_okf.py <bundle>` — must be 0 ERROR.

If `fastembed` model download fails, see `references/index-design.md` §Embedding for the fake-embed-fn fallback (tests only).
