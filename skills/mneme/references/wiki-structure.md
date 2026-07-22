---
type: Reference
title: mneme wiki structure
description: How a growing OKF wiki bundle is organized and curated.
---

# wiki structure

```text
<bundle>/
├── index.md          # progressive directory; root may declare okf_version
├── log.md            # newest-first dream timeline
├── sources/          # OKF type: Source provenance pages
├── raw-sources/      # immutable artifacts; Markdown originals use *.md.raw
├── concepts/         # atomic concept pages
├── references/       # distilled external sources
├── summaries/        # cross-concept syntheses
├── topics/           # curated topical maps
├── archive/          # superseded pages retained for history
└── .mneme/           # disposable, gitignored SQLite index
```

Keep one concept per page and use stable lowercase slugs. Cross-link with
absolute bundle-relative paths. Use ordinary `Topic` pages for reading maps;
do not mirror every tag into a generated page. Keep the content tree easy to
walk from `index.md`; a derived FTS5 or L2 index accelerates navigation but
does not own facts or justify deep manual nesting.

Every `.md` file under the bundle, including `sources/`, is an OKF concept page.
Opaque artifacts are not indexed as knowledge pages. Appending `.raw` to a
Markdown artifact changes only its filename, not its bytes.
