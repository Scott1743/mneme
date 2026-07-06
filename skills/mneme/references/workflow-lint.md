---
type: Reference
title: mneme lint workflow
description: Curate the wiki for conformance and quality.
---
> The `mneme lint` CLI runs the validator + curation agent. This doc is the agent's spec. See `wiki-structure.md` + `index-design.md`.

# lint workflow

- **Hard errors** (from validator, must fix): `no-frontmatter`, `empty-type`, `no-bundle`.
- **Warnings** (curate, ask before fixing): `broken-link` (target missing — create the page or fix the path), `missing-index` (no root `index.md` — generate one), `bad-reserved` (empty `index.md`/`log.md`).
- **Curation heuristics** (agent judgment, propose only): contradictions between pages, stale `timestamp` with no log entry, orphan pages (nothing links to them — link them or merge), important concepts with no page, missing cross-links between related pages.
- **Apply fixes only with user approval**; re-run the validator after.
