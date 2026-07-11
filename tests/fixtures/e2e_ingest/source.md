# OKF v0.1 — Quick Summary

OKF (Open Knowledge Format) is a directory-of-Markdown format for
representing linked concept pages. A bundle's `index.md` enumerates the
top-level concepts; `log.md` records ingest events newest-first; and each
concept page lives under `concepts/<slug>.md`.

Two facts that make OKF different from a plain wiki:

1. Frontmatter is required and must declare a `type` (Concept /
   Reference / Summary / Source).
2. Cross-references use absolute bundle-relative paths so moving a
   file does not break a reference to it.
