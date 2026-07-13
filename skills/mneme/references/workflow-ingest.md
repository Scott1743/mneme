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
7. **Reindex**: `Bash: python3 ~/.claude/skills/mneme/scripts/mneme.py reindex`. First-time L2 use: if `sqlite-vec` / `fastembed` are missing, the CLI prints a one-line install instruction. Subsequent runs use cached deps.
8. **Validate**: `Bash: python3 ~/.claude/skills/mneme/scripts/mneme.py lint <bundle>` — must be 0 ERROR.

If L2 deps are missing, the user runs `pip install 'sqlite-vec>=0.1.9,<0.2' 'fastembed>=0.8.0,<0.9'` once and re-runs the command. There is no auto-install.
