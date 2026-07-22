---
type: Reference
title: mneme dream workflow (approved write side)
description: Apply an approved dream preview while preserving sources and OKF invariants.
---

# dream workflow (after approval)

Load this procedure only after the user approves the audit and concrete change
preview shown by the main skill. The `mneme dream` CLI remains read-only; all
approved writes use the host agent's native `Write` and `Edit` tools.

1. Re-read the approved paths and scope. If a material expansion is needed,
   stop and preview it before requesting additional approval.
2. Copy the original source unchanged to `<bundle>/raw-sources/<artifact-name>`.
   Preserve the basename except when it ends in `.md` (case-insensitive): append
   `.raw`, so `paper.md` becomes `paper.md.raw` and remains outside OKF's
   concept-document namespace. A converted text file is a reading aid, not a
   replacement for the original. If the destination exists with different
   bytes, stop instead of overwriting.
3. Create or update `<bundle>/sources/<slug>.md` as an OKF `type: Source` page.
   It includes `title`, `description`, at least one `tags` value, `timestamp`,
   and `resource: /raw-sources/<artifact-name>`, plus provenance in the body.
   Link distilled pages to this Source page rather than directly to the opaque
   artifact.
4. Write or edit one page per atomic concept. Mneme-written pages include at
   least `type`, `title`, `description`, one or more `tags`, and `timestamp`;
   include `resource` when a canonical source is available.
5. Preserve unknown frontmatter keys on existing pages. Express relationships
   with absolute bundle-relative Markdown links.
6. Update `<bundle>/index.md` under the section matching each page's `type`.
7. **Prepend** `<bundle>/log.md` with
   `## YYYY-MM-DD dream | <source or curation title>` and a concise summary.
8. Run `mneme lint --bundle <bundle>`. Fix only approved-scope errors; report
   anything requiring new judgment.
9. Rebuild the selected index after validation. Use default `mneme reindex`
   unless the user explicitly selected L2 for this bundle; then use
   `mneme reindex --l2`. Do not install missing L2 dependencies.
10. Re-run `mneme dream --bundle <bundle> --json` and report remaining audit
   candidates.

Never run `git add`, `git commit`, or `git push`; never merge, archive, delete,
or overwrite facts from an automated score. An external OKF page without tags
remains consumable: missing tags are a Mneme writer warning, not an OKF error.
