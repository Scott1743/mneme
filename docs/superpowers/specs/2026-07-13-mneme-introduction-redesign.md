# Mneme 2.0 — Introduction Page Redesign Brief

> **Status:** approved by the user ("你需要改 introduction，第二部分用 skills.sh 安装方式 + 提示词示例；第三部分要 娓娓道来。页面排版真的丑，你没点审美么？").
> **Date:** 2026-07-13.
> **Aesthetic Priority:** Type, whitespace, narrative cadence over card walls and CLI dumps.

---

## 1. Why this rewrite

The current `introduction/index.html` shows Mneme as a CLI + RAG product. Three problems:

- Hero shouts "轻量化 LLM Wiki" then dumps two generic lede paragraphs; the visitor scans once and leaves.
- §2 reads like a CLI cheat sheet (`python3 … init`, `… reindex`, `… search`). The product surface is supposed to be `dream` and `search`.
- §3 dumps code snippets. Snippets are not the point. The point is the LLM-Wiki-not-RAG thesis and what it feels like to maintain one.

The 2.0 rewrite fixes all three. Mneme is a knowledge product whose user is an agent. The page should feel like an editorial introduction to that idea, not a CLI reference card.

## 2. Hero

**H1:** `Mneme` — single word, big serif. No tagline below it; let the word breathe.

**One sentence lede (no bullet, no chip row):**

> 一座由 Agent 增量维护的本地 Markdown 知识库。
> 不是每次提问都重新检索——是让 Agent 把读过的资料编译进一棵可以反复行走的概念树。

**Single CTA** (one button, not a row of three):

```
[ npx skills add Scott1743/mneme ]   ← visible without hover, copy-paste-ready
```

Below the button, one plain-text line: `~/.claude/skills/mneme/ · MIT · 2.0.0` — no badge pills, no chip row.

**Visual anchor:** a small ASCII glyph of the L1 stack in the right margin, mono, dimmed. Keeps the page from looking like it lost the previous illustration.

```
   .mneme/index.db    ← sqlite3 + FTS5 (default)
   .mneme/cache/      ← agent memory; never the source of truth
   wiki/              ← what you read; what you git
```

## 3. § 2 — 先和 Agent 聊

**Single column. No CLI list.**

Install (one line):

```
npx skills add Scott1743/mneme
```

Then prose: `安装到你的 Agent skills 目录之后，重启会话即可。Mneme 没有独立窗口、没有常驻服务、没有命令行仪表——你和你的 Agent 聊天就是了。`

Then a chat snippet (fenced, narration style — *not* a CLI invocation):

```
你:  我刚读了几篇关于 OKF 的文章，帮我把它们收进我的 wiki。

Agent:  好。把文章路径发给我吗？我会创建一个新 wiki，按 OKF 协议写
        摘要页，互相链接，更新 index，最后跑一遍 lint。
```

```
你:  我三周前看过一篇东西，里面讲到 SQLite FTS5 怎么建倒排索引——
    帮我找回来。

Agent:  让我读你的 wiki 看看。
        ← 命中 「SQLite 内部」「FTS5 vs LIKE」两组概念页
        它们都引用了一份来源笔记——给你看摘要片段与原始资料路径。
```

Two short paragraphs after the snippet:

- **dream** 把读过的资料编译成本地 Markdown；Agent 写 page、写 link、写 tag，你说了算。
- **search** 在你的 wikik 里走——读索引、读 tags、走链接、必要时打开 L1 FTS5；找不到就说没找到，不编。

That's the entire §2. No more cards, no more `<pre>` walls, no more "`python3 ~/.claude/skills/mneme/scripts/mneme.py` …" copy.

## 4. § 3 — 娓娓道来

> 这是 Mneme 真正想讲的事：知识不是每次提问都重新检索的——它是被你的 Agent 编译进一棵你看得见、改得了、行得通的树。

Then a single, slow paragraph (~120 words):

> 想象一下你读过的所有笔记、论文摘录、对话笔记——它们被放在一个本地文件夹里，被 Agent 加上 YAML frontmatter，被指向相邻的概念页，被链接、被标记。你可以用 `git` 一样 diff 它，blame 谁改了哪一行，branch 出一个实验分支。所有你想得起来的"我三周前看的那个东西"都被存在那里，不是被重新检索。
> 
> RAG 每次都重新发现知识——不持久、不积累、不互相引用。LLM Wiki 把知识编译一次：以后每次提问都是在已经存在的东西上行走的，不是在空仓库里爬的。

Continue (~90 words):

> Mneme 让这件事对个人和团队都变得轻：本地存储、纯 Markdown、零常驻、零云依赖。你用 Agent 维护它；Agent 写、Agent 链、Agent 审 lint，你只是和 Agent 聊。规模上来时打开 SQLite FTS5；想要向量召回就装 [optional] v2.1 才会出现的语义索引。索引是垃圾，你不需要它也能用——它只是帮你走得更快。

Then a 3-card row is allowed *here* (after narrative earned it):

- **dream** — 把资料编译进 wiki
- **search** — 在已有 wiki 里走
- **lint** — 周期性地指出矛盾、孤儿、漂移

Each card ≤ 80 words, no CLI call inside.

## 5. § 4 — 你为什么可能需要它

Prose only, ≤ 200 words. Three sentences max in tight rhythm:

> 一份查得到、改得了、被 Agent 维护着的知识，比随时重新检索的 RAG 库更接近"思维的外接硬盘"。Mneme 想做的就是这件事——把它说出来的语言是 OKF v0.1，把它写出来的工具是一个站在你 Agent 旁边的轻量 skill。

## 6. § 5 — Friends

Keep the existing 森林密语 / 塔罗树洞 block but strip the bullet list. One paragraph, one `<aside>` block.

## 7. Aesthetic rules (binding)

- **No card grids.** Cards are allowed in §3 after narrative earns the right; not in §1, §2, §4, §5.
- **No CLI invocation in body text.** References to `mneme dream` or `mneme search` are fine; full bash invocations are not.
- **No badge / chip rows.** Versions, license, OKF respect go inline as a single dotted line of plain text.
- **No code dumps.** Code appears only at the install line and inside the chat snippet.
- **No "naive RAG" anywhere.** This entire page must read as LLM-Wiki-not-RAG.
- **No L2 path mentions.** Page says "optional L1 (FTS5) ships in 2.0; semantic L2 ships in 2.1 — index is always disposable." Not BGE/vec/fastembed names.
- **Whitespace does the work.** Use `clamp()` for type scale, generous line-height (1.7+), max content width 720px inside main. Hero h1 has 1em of letter-spacing on the side of negative (-0.01em), not loose.
- **One font pair.** Keep STKaiti/KaiTi for headings + PingFang SC for body. Do not introduce new typeface.
- **Color palette:** paper, ink, hairline, pine-teal accent, okf-blue link. No new hue.
- **Dark mode parity.** Existing `prefers-color-scheme: dark` block is fine; the rewrite must not break it. Hint: when changing tokens, swap both light and dark blocks in the same `Edit`.

## 8. What stays / what goes

Stays:
- Brand tokens in `:root` (paper/ink/serif-sans pair).
- Color scheme dark/light parity.
- Self-contained CSS (no CDN, no `@import`, no `url(http…)`).
- §5 friend-card block (renamed to §5 "朋友项目").
- Footer with repo / MIT / CHANGELOG / skills.sh.

Goes:
- "v1.1.0" badge → replace with "2.0.0" inline.
- Three-card "三块场景" → drop entirely; merge "心理咨询" hint into §5 if needed.
- Four-role grid (`ingest / query / lint / search`) → at most three, only at end of §3, no CLI in description.
- BGE / sqlite-vec / lazy-install language.
- L2 demo lines and `python3 ~/.claude/skills/mneme/scripts/mneme.py init ~/my-wiki` block.
- "## 关键代码片段" subsection.
- `# 基础约束` and "三层架构" ASCII dump block at hero — kept but rewritten lighter in §3.

## 9. Acceptance

- Page loads with `python -m http.server` (no asset deps).
- Light + dark mode readable at 980px and at 560px (existing breakpoint).
- `tests/test_introduction_page.py` (1 h1, 3 sections with ids `初衷 / 安装 / 原理`, link integrity) still green after rewrite.
- `tests/test_introduction_rewrite.py` (no `--l2`, no `sqlite-vec`, no `fastembed`, no "naive rag") green.
- Hero h1 is exactly one word, h1 not "Mneme"; lede ≤ 2 short paragraphs, no chip rows.
- §2 contains: install line + 1 chat snippet + 2 short paragraphs (about `dream` and `search`) only.
- §3 leads with one full-width narrative paragraph; any cards appear only after ≥ 2 sentences of prose.
- Footer ≤ 4 lines.
- File size after rewrite: ≤ 14 KB (current is 14.4 KB so we have slack for cleaner prose).

## 10. Implementation notes

- Edit `introduction/index.html` in one go; reuse existing `:root` tokens.
- Update `introduction/README.md` to reflect that this page is the editorial face of Mneme, with a 1-page authoring guide (target audience, tone: literary-and-concise, "do not bulk with badges", exit criteria = Acceptance §9).
- Update `tests/test_introduction_page.py` only if structural assertions change (3 sections with the IDs the file actually uses after the rewrite; let the test follow the file, not the other way round).
