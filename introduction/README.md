# Introduction page (GitHub Pages)

This directory holds the Mneme landing page — a self-contained,
inline-CSS, no-CDN HTML page that GitHub Pages serves at:

**https://scott1743.github.io/mneme/**

The page is deployed automatically by
[`.github/workflows/pages.yml`](../.github/workflows/pages.yml) on every
push to `main` that touches `introduction/**`.

> Why `/` and not `/introduction/`? `actions/upload-pages-artifact@v3`
> packages `introduction/index.html` as the artifact root, and Pages
> serves it at the project site root. The `introduction/` directory
> stays in the repo purely for code organization.
