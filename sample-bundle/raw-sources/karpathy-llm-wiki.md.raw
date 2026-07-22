> Source: Andrej Karpathy, *LLM Wiki* (GitHub gist, 2026-04-04).
> URL: https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f
> This file is a verbatim raw excerpt of the gist. It is immutable: an OKF
> Source pointer in `sources/karpathy-llm-wiki.md` references it via `resource:`.

# LLM Wiki

Obsidian is the IDE. The LLM is the programmer. The wiki is the codebase.

Compile knowledge once. The compiled wiki then compounds on every search
you do and on every file you add — knowledge doesn't degrade or repeat
the same retrieval cost each time. You curate sources; the LLM curates
the wiki.

## Three layers

1. **Raw sources** — the inputs (papers, notes, transcripts, code). LLM
   only reads them.
2. **The wiki** — LLM-generated, LLM-maintained, interlinked Markdown
   pages distilled from sources.
3. **The schema** — the rules the LLM follows (`CLAUDE.md`,
   `AGENTS.md`, etc.) so its edits stay coherent over time.

## Three operations

- *Ingest*: drop in a new source → LLM discusses, drafts concept pages,
  updates `index.md` / `log.md`, cross-links related pages.
- *Query*: ask the wiki → LLM finds relevant pages, reads them, cites.
- *Lint*: periodic health check → orphan pages, contradictions, missing
  cross-references.

## Why not RAG

RAG re-discovers the same knowledge with every query. The wiki is
compiled once — search costs flatten over time and the corpus only gets
richer.

## Caveat

LLMs cannot natively read embedded images inside Markdown in a single
pass. For image-heavy inputs, extract the text first.
