---
type: Reference
title: mneme ingest workflow
description: Detailed rules for ingesting a source into the wiki.
---
# ingest workflow

- **Slug**: derive from source filename, lowercase, spaces→hyphens. `My Note.md` → `sources/my-note.md`.
- **Placement**: concept pages go under a topical subdir (e.g. `concepts/`, or a domain dir). Mirror the source's theme; create a dir if none fits.
- **Type choice**: `Reference` for a distilled external source; `Concept` for an idea you extract; `Summary` when you synthesize across multiple sources; `Source` is the raw copy in `sources/`.
- **One source → multiple pages**: a rich source may yield 5–15 pages (one per distinct concept). Always link them to each other and to existing pages.
- **Cross-links**: absolute bundle-relative form (`/concepts/okf.md`) — stable when files move within their subdir.
- **index.md**: add one entry per new page, description copied from the page's frontmatter `description`.
- **log.md**: `## YYYY-MM-DD ingest | <source title>` then bullet lines of what was created/updated.
- **Validate last**: `python3 scripts/validate_okf.py <bundle>` must report 0 errors before you stop.
