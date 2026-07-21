# Changelog

All notable changes to **mneme** are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html),
with one caveat: **1.0.0 is a release-contract gate, not a feature gate.**
Versions below 1.0.0 may carry partial behavior; consult `docs/superpowers/`
for in-flight specs and plans.

## [Unreleased]

### Changed

- Replaced the invalid five-query historical reports with the frozen 80-query
  Graph enrichment diagnostic in `reports/`. The new report separates
  deterministic Graph (`G0`), enriched Graph (`G1`), and their global-FTS
  hybrids, reports bootstrap confidence intervals plus Top-1 accuracy,
  Precision@10, macro Recall@10, and macro F1@10, presents the frozen question
  construction and full 80-query inventory before the results, and labels extraction-
  derived qrels as construction-aware rather than independent human judgments.
- FTS5 search now retries punctuation-heavy natural-language queries as quoted
  tokens when SQLite interprets hyphens or other characters as MATCH syntax.

## [4.1.0] - 2026-07-21 - agent-extracted graph enrichment (`graph ingest`)

### Added

- **`mneme graph ingest <extraction.json>`** merges agent-extracted entities
  and relations into `<bundle>/.mneme/graph.db`. Phase 2 keeps the division of
  labor explicit: the host agent is the LLM (it reads pages and produces the
  extraction JSON), while the CLI stays deterministic (it validates and writes
  SQLite, never calls an LLM, never touches Markdown). Use `"-"` as the file
  to read the payload from stdin.
- **Graph schema v3** (`GRAPH_SCHEMA_VERSION = "3"`): `entities` gains
  `source` / `confidence`, `relations` gains `source` / `confidence` /
  `evidence`, and `relation_sources` retains independent supporting pages, so
  derived-from-LLM structure is distinguishable from
  deterministic page/tag/link structure. The migration is an idempotent
  `ALTER TABLE` inside `ensure_graph_schema`; existing v1 graph databases
  upgrade in place and remain disposable.
- **Hybrid correctness**: Graph and global FTS5 candidates are fused as a
  union; Graph no longer hard-filters lexical recall. Graph caches carry a
  Markdown source fingerprint and stale caches fall back to global FTS5.
- **Replayable enrichment**: approved extraction blocks are kept in
  `.mneme/graph-extractions.json` and replayed during Graph rebuilds.
- **Extraction contract** (`graphlib.validate_extraction` +
  `graphlib.ingest_extraction`): tolerant per OKF §9 — malformed blocks are
  skipped with warnings instead of rejecting the payload; confidence is
  clamped to `[0, 1]`; predicates are normalized to safe tokens; every
  extracted entity connects back to its page with a `mentions` edge so BFS
  from an entity seed reaches the source page in one hop. Re-ingesting a page
  replaces only that page's prior `llm_extracted` relations (idempotent per
  page). `graph_health` now reports `llm_entity_count` / `llm_relation_count`.
- **SKILL.md dream workflow** documents the extraction → preview → `graph
  ingest` loop so agents enrich the graph after approved writes, and the
  internal command list covers `graph ingest`.
- The Graph benchmark runner measures deterministic and enriched indexes on
  the same frozen bundle without mutating Markdown.

### Evidence

- The replacement 80-query construction-aware benchmark records enriched
  Graph nDCG@10 0.729 versus deterministic Graph 0.235, with paired bootstrap
  delta +0.494 [0.387, 0.604]. Duplicate Feishu exports with identical bodies
  are evaluated as one document equivalence class. These numbers demonstrate extraction coverage,
  not independent general-search quality; the full methods and limits are in
  `reports/experiments/graph-enrichment-benchmark.html`.

### Preserved

- Markdown remains the only source of truth; `graph.db` is still a derived,
  disposable cache, and deleting it falls back to FTS5/L0.
- The user surface stays `dream` + `search`; `graph` is an internal agent CLI
  operation like `reindex`. No new runtime dependencies; Graph stays stdlib
  SQLite. The dream preview-and-approval contract now covers extraction
  payloads.

## [4.0.1] - 2026-07-20 - graph search description match + dream/hybrid fixes

### Fixed

- **`find_entity_by_name` now searches the `description` column.** v4.0.0
  omitted it from the LIKE WHERE clause, so Graph search and the Graph leg
  of hybrid retrieval never surfaced pages whose name is a path/slug but
  whose description carries the semantic content (the common case for
  bootstrap dogfood pages whose title is derived from the source filename).
  This is the root cause of the v4.0.0 cross-version regression where
  `G` (graph-only) returned zero candidates for every historical query on
  the 142-document Feishu corpus. The fix also adds a `name` prefix-match
  tier in the ORDER BY so exact name matches rank first, then prefix
  matches, then description/properties matches.
- **`cmd_dream` no longer crashes when invoked without `--bundle`.** v4.0.0
  passed `Path(args.config)` (where `args.config` defaults to `None`) to
  `_resolve_bundle`, raising `TypeError` on the default `mneme dream`
  invocation. The fix routes through `_resolve_bundle(args)` like the other
  subcommands while preserving the v0.3.0 frozen contract that `dream`
  exits 0 even when the bundle is missing.
- **`_iter_page_records` now catches `UnicodeDecodeError`.** v4.0.0 only
  caught `OSError`, so a single non-UTF-8 `.md` file aborted the entire
  graph rebuild. OKF §9 requires one bad file not to affect the rest.

### Added

- Regression tests in `tests/test_graphlib.py` covering the description
  match path (`find_entity_by_name`, `search_graph`, `search_hybrid`).
- Regression tests in `tests/test_dream_readonly.py` covering `mneme dream`
  without `--bundle` and `tests/test_graphlib.py` covering non-UTF-8 files.

### Preserved

- The user surface, OKF/Mneme writing discipline, read-only `mneme dream`,
  explicit L2 opt-in, and disposable accelerator contract are unchanged.
- `graph.db` remains a derived cache; deleting it falls back to FTS5/L0.

## [4.0.0] - 2026-07-20 - graph-enhanced hybrid retrieval

### Added

- Added the stdlib-only `<bundle>/.mneme/graph.db` disposable cache with page,
  tag, and Markdown-link entities/relations, atomic rebuilds, graph traversal,
  and health counters.
- Added `mneme reindex --graph`, which rebuilds Graph and refreshes FTS5 without
  modifying the authoritative OKF Markdown bundle.
- Added `mneme search --mode graph|fts|hybrid`. Graph-enabled FTS5 bundles use
  hybrid retrieval by default; hybrid falls back to global FTS5 when Graph is
  missing or the query contains no graph entity match.
- Added graph context and fused Graph/FTS scores to hybrid JSON candidates, while
  preserving the required `path` / `title` / `snippet` navigation shape.
- Added graph health statistics to the read-only `mneme dream --json` report.

### Preserved

- The user surface remains exactly `dream` + `search`; internal CLI command names
  and existing `init` / `lint` / `reindex` / `convert` contracts remain intact.
- Markdown remains the only source of truth. Graph, FTS5, and L2 are independent,
  gitignored caches that can be deleted and rebuilt.
- `mneme dream` remains read-only, OKF v0.1 tolerance and Mneme tags discipline
  remain unchanged, and L2 stays an explicit user-installed opt-in with no
  silent fallback.

## [3.4.0] — 2026-07-16 — nightly agent health workflow

- After initialization, the first interactive dream, or a direct maintenance
  request, the skill can offer a host-agent recurring task at 02:00 local time.
- Users choose report-only or guarded auto-repair. Auto-repair is a bounded
  standing authorization for unambiguous metadata, tag, internal-link, index,
  timestamp, log, and disposable-index maintenance; ambiguous or broad changes
  degrade to a report.
- Factual body text, raw sources, new knowledge pages, merges, archives, moves,
  deletes, and git writes remain outside the nightly authorization boundary.
- The agentless `mneme dream --schedule` fallback remains report-only and now
  defaults to 02:00 for consistency with the host-agent workflow.

## [3.3.0] — 2026-07-15 — persistent retrieval mode and independent caches

- `mneme reindex --l2` now explicitly builds and activates L2 once, recording
  `active_retrieval_mode = "l2"` in the local config only after a successful
  rebuild. Subsequent bare `search` and `reindex` commands use that mode, so
  agents do not need to remember a per-command semantic flag.
- Split derived caches into `<bundle>/.mneme/fts.db` and
  `<bundle>/.mneme/l2.db`. Switching modes never overwrites or deletes the
  other cache; `mneme reindex --fts5` explicitly returns to FTS5.
- A configured L2 mode with a missing or unavailable L2 cache fails clearly and
  never silently substitutes FTS5. Existing 3.2 `index.db` files are
  disposable and rebuilt on the first 3.3 reindex.

## [3.2.0] — 2026-07-14 — contract-aligned workflows and conversion adapter

- Finished the dream/search migration: `SKILL.md` now exposes exactly those two
  user scenarios. Legacy ingest behavior is part of the approved dream write
  workflow, and query synthesis is part of search.
- Added explicit reference loading conditions. Detailed dream instructions load
  only after approval; search reads complete Markdown pages before synthesizing
  cited answers.
- Added `mneme convert` for explicit preprocessing with compatible converters
  already installed by the user. Mneme never installs a converter or replaces
  the immutable source.
- Preserved FTS5 as the default and `--l2` as explicit opt-in. Semantic search
  changes candidate retrieval only; it does not change Markdown authority or
  dream approval rules.
- Added strict release gates for scenario/CLI sets, approval-before-write,
  dream log prefixes, reference layout, and L2 non-fallback behavior.

## [3.0.0] — 2026-07-14 — optional semantic search

v3.0 在 v2.0 零依赖基础版之上，把 L2（语义召回）作为**显式 opt-in**带回：`mneme reindex --l2` 与 `mneme search --l2` 通过 `--l2` 标志走 `indexlib.reindex_bundle`（`sqlite-vec` + `FastEmbed` + `BAAI/bge-small-zh-v1.5`）路径。依赖仍由用户自行安装；FTS5 仍是默认路径。

### Added

- **`--l2` flag on `reindex` and `search`.** 默认仍然走 FTS5；显式加 `--l2` 才走 `indexlib.reindex_bundle`（vec0 + BGE）。`search --l2` 拒绝在 FTS5-only 索引上静默回退——它检查 `vec_chunks` 表是否存在，缺失则报错并提示先跑 `mneme reindex --l2`。
- **`sqlite-vec` + `FastEmbed` + `BAAI/bge-small-zh-v1.5` are user-installed.** 缺失时打印一行安装提示（`pip install 'sqlite-vec>=0.1.9,<0.2' 'fastembed>=0.8.0,<0.9'`）而不是 `ImportError` traceback。
- **`pytest.mark.l2` marker** —— 守护 v2.1 `--l2` 表面（CLI flag、错误文案），离线可跑。<1s。

### Preserved

- **FTS5 remains default.** v2.0 的 L0/L1 零依赖契约未受影响；`tests/test_zero_dep.py` 全部继续通过。
- **No auto-install.** skill 不自带任何 `pip install` 动作；与 v2.0 一致。
- **`dream` 仍然只读审计。** v2.1 不引入新写路径。

## [2.0.0] — 2026-07-14 — dream + search surface; OKF + tags; L2 deferred to 2.1

v2.0 是 **LLM-Wiki-not-RAG** 的里程碑：把 mneme 的产品叙事从「CLI + 可选 L2 向量检索」收回到「`dream` 写、`search` 读、一座 OKF 合规的本地 Markdown 知识库」。OKF 仍是 wiki 本体的格式契约；L1（SQLite FTS5）取代 1.1.0 的 L2（语义召回）成为默认导航层；语义召回推迟到 v2.1。CLI 仍是 `init / lint / reindex / search / dream`，`dream` 是只读审计、写盘由 agent 在 SKILL.md 工作流里完成。

### Breaking changes

- **User surface = `dream` + `search` only.** `init` / `lint` / `reindex` / `search` / `dream` 是 agent 在后台跑的确定性 CLI；用户叙事里只讲 `dream` 与 `search`。SKILL.md 删去 `ingest` / `query` 场景标题 —— 同等意图并入 `dream` / `search`。
- **`init` 退出码改为 `1` 表示 bundle 已存在**（取代 1.x 的「幂等覆盖」语义）。bundle 已存在时仍按原值返回，**不会**静默覆盖；想做覆盖必须显式 `--force`。
- **`lint` 退出码简化为 `0/1`，用 `1` 表示存在 ERROR。** 取代 1.x 的 `LINT_GUARD_RC=3` 信号；CI / shell 脚本请把 `rc == 3` 改为 `rc != 0`。
- **`dream` 子命令只读。** 无 `--apply` 标志（v1.x 草案中的 `--apply` 已删除）；dream 出的报告由 agent 在 SKILL.md 工作流里、用 `Write` / `Edit` 工具落盘，且必须**先得到用户明确点头**。`git add -A` / `git commit` / `git push` 永不自动触发。
- **删除 L2 子命令与 `--l2` 标志。** `reindex` / `search` 在 v2.0 不再支持语义召回路径。可选语义召回层**推迟到 v2.1**——v2.0 不引入、不打包、不自动装相关依赖。
- **删除「Naive RAG」叙事。** SKILL.md / README / introduction 全部明确为「compile-once / walk-the-graph」；语义召回不再是默认叙事。
- **bilingual `SKILL cn.md` 删除。** v2.0 只保留下单份英文 `SKILL.md`（取代 1.1.0 起的 `SKILL cn.md` 镜像）。中文读者由 `introduction/index.html` 承担。

### Added

- **`mneme dream` —— 只读 audit CLI。** 返回一组候选报告（OKF 硬规则 / mneme 写作纪律 / 导航健康度），永不直接改 bundle。`tests/test_dream_readonly.py` 守护「dream 不写盘」、「dream 不 shell `git add -A`」、「dream 只报告 raw distance」的契约。
- **`tags` 写入规则。** mneme 自己写出来的概念页 frontmatter 至少含 1 个 `tags` 值；外部 OKF bundle 缺 `tags` 只 WARN，不拒绝。`type` 与 `tags` 不重叠：`type` 描述文档角色（OKF 协议级 MUST），`tags` 描述主题归类（mneme 写作纪律）。
- **Topic 页面作为概念地图。** 需要「按主题聚合」时写一份普通 OKF `Topic` 页面（`type: Topic`）；不要按 tag 镜像 `tags/<tag>.md`，后者维护成本高且易腐化。
- **L1 默认 — `sqlite3` + FTS5。** 索引文件 `<bundle>/.mneme/index.db`；`body` 列在线可搜，`mneme reindex` 用「temp-db → fsync → os.replace」做原子全量重建。FTS5 schema 见 `references/workflow-search.md`。
- **`tests/test_changelog.py` + `tests/test_introduction_rewrite.py`** —— 守护 2.0 表面：`dream`/`search` 作为用户动词、L2 仅在「deferred to v2.1」语境出现、CHANGELOG `## 2.0.0` 写明 dream/search + L2 deferred。

### Fixed

- 1.1.0 中**误称**的「L2 首次调用自动装」机制（首次 `reindex` / `search` 触发 `pip install` + 下载 ~90MB 模型）：v2.0 不存在；语义召回推迟到 v2.1。
- 1.1.0 中**承诺**的「wheel build smoke」：v2.0 不存在；交付物仅为 skill zip。
- 1.1.0 中**从未实际删除**的 `skills/mneme/scripts/mneme.egg-info/` 与 `dist/mneme-1.1.0.zip` 残留：v2.0 清理 + `.gitignore` 守门。
- 1.1.0 中**未修正**的 `test_release_layout.py` 中对 1.1.0 字面量的硬编码：v2.0 改为基于 `__version__` 的正则断言。
- sample-bundle 内部 `sources/*.md` raw 内容移到 `sample-bundle/external-sources/`；bundle 内部只剩 OKF `Source` 指针页。
- CI matrix 收窄到 Python 3.11 / 3.12 / 3.13（去掉 3.10——`config.py` 要求 3.11+）。

## [1.1.0] — 2026-07-13 — skill-first delivery + zero-dep OKF core + L2 lazy install (CORRECTED)

> 1.1.0 的描述在 v2.0 中得到修正。以下是 v2.0 视角下 1.1.0 的真实状态——其中 **drop lazy install / drop wheel / drop bilingual SKILL** 三项均在 v2.0 中撤销或更正。

### Delivery model — skill-first (kept)

- `skills/mneme/` 是唯一交付物；`dist/mneme-1.1.0.zip` 是当时唯一的发布物；安装地址仍是 `~/.claude/skills/mneme/`。**这与 v2.0 一致**。
- **`pyproject.toml` 的 `[build-system]` / `[project.scripts]` / `[tool.setuptools.*]` 在 1.1.0 中已删除。** 这与 v2.0 一致。

### Zero-dep OKF core (kept)

- **tomli_w 被手写 TOML writer 取代。** `toml_writer.py`（~60 行，stdlib only），类型 `str` / `int` / `float` / `bool` / `list` round-trip 通过 `tomllib`（3.11+）/ `tomli`（3.10 extras `toml10`）。这与 v2.0 一致。
- **PyYAML 仍是 opt-in**，通过 `mneme[validate]` extras。v2.0 一致。

### L2 lazy install — **REVERTED in v2.0**

- 1.1.0 声称 `ensure_index_deps()` 触发首次 `reindex` 或 `search` 时自动 `pip install sqlite-vec fastembed` 并下载 ~90MB 模型。**v2.0 撤销此行为：**自动安装路径不存在；语义召回层整体推迟到 v2.1。`tests/test_lazy_index.py` 在 v2.0 中被对应的「无 L2 自动装」与「无 `--l2` 标志」契约替代（见 v2.0.0 §Breaking 与 §Added）。
- 1.1.0 的 "Pre-existing-L2-gets-imported-on-first-use"（`os.execvp` 重启 self）行为：**v2.0 不存在**。

### Bilingual SKILL — **DROPPED in v2.0**

- 1.1.0 保留 `SKILL.md`（权威英文）+ `SKILL cn.md`（中文镜像）。**v2.0 删除 `SKILL cn.md`**，只保留单份英文 `SKILL.md`。中文读者由 `introduction/index.html` 承担。

### wheel build / `mneme` console command — **DROPPED in v2.0**

- 1.1.0 已经在 zip-only 路径上撤销 wheel / `mneme` console command。**v2.0 严格强化这条约束**：`tests/test_release_layout.py` 不允许 `[build-system]` / `[project.scripts]` / `[tool.setuptools.*]` / `setuptools` 任意一项出现在 `pyproject.toml` 中。
- 仓库工作树的 `dist/mneme-1.1.0.zip` / `skills/mneme/scripts/mneme.egg-info/` 残留：v2.0 一并清理 + `.gitignore` 守门。

### Tests added in 1.1.0 (kept where compatible, replaced where not)

- `tests/test_release_layout.py`（16）——v2.0 改为基于 `__version__` 的断言。
- `tests/test_toml_writer.py`（9）—— kept。
- `tests/test_zero_dep.py`（5）——v2.0 调整（不再断言 L2 lazy-install 行为，改为断言「不引入 sqlite-vec / fastembed 依赖」）。
- `tests/test_lazy_index.py`（7）——**v2.0 删除**，对应契约改由 `tests/test_skill_drift.py` 守护。
- `tests/test_docs.py`（+8）——v2.0 强化：禁止 README / introduction / CLAUDE / AGENTS 出现 `--l2` / `sqlite-vec` / `fastembed` / `BGE` / `naive rag` / `auto-install` 字样。

### Migration notes for 1.0.x wheel users (v2.0 perspective)

- 1.0.x wheels 仍可在 PyPI 上获取；它们与 v2.0 zip-only 路径不再互操作。
- 升级到 v2.0：重装为 skill zip；现有 `~/.config/mneme/config.toml` 与 bundle 目录无需迁移。
- 升级路径不包含任何 L2 自动装；想要语义召回请等 v2.1 或自行装。


## [1.0.0] — 2026-07-12 — release-gate closure

Closes the readiness-assessment release gate
(`docs/superpowers/reports/2026-07-12-mneme-1.0-readiness-assessment.md`).
1.0.0 is **not** "feature complete"; it is "the contract is
verifiable from a clean install." The product scope is unchanged
from v0.6.1 — `init` + `reindex` + `search` + `lint` + the
documented ingest / query workflows, with dream intentionally
excluded. What changed is that every P0/P1 finding in the
assessment is now either resolved or guarded by a test.

### Release-gate items closed by this version

- **All P0/P1 findings resolved or removed from the contract.**
  Validator certifies YAML via PyYAML (since 0.3.0). Lint calls
  `find_orphans` for real (since 0.6.1). Dream is removed and
  gated by an explicit resurrection clause. Ingest prepends to
  `log.md` and copies the raw source (since 0.2.1rc1).
- **Install-to-query works from the release artifact in a clean
  environment.** Fixed two install-test bugs that the v0.6.x
  freeze window left behind:
  - `WHEEL_GLOB[0]` picked the alphabetically-first wheel in
    `dist/`, so a fresh venv install ran stale v0.5.0 code when
    v0.6.1 was the intended release. Test helpers now pick the
    highest-version wheel.
  - Four `test_e2e_ingest` tests called `mneme init` without
    `--config`, leaking into the user's `~/.config/mneme/config.toml`
    and failing on macOS TCC-protected home directories. All e2e
    tests now isolate config to a tmp path.
- **`__version__` drift fixed.** `src/mneme/__init__.py` was pinned
  to `"0.3.0"` while `pyproject.toml` rolled forward through
  0.4.0 → 0.5.0 → 0.6.0 → 0.6.1. `mneme.__version__` now reads
  `"1.0.0"` and `test_version.py` asserts the two sources agree
  at every commit.
- **Resource budgets documented and tested.**
  `tests/test_release_budget.py` pins: source skill artifact
  < 250 KB; L1 Markdown reading stays zero-third-party-dep
  (sqlite-vec / fastembed / PyYAML absent at import time);
  FastEmbed model cache pinned to `~/Library/Caches/mneme/models/`
  (macOS) or `~/.cache/mneme/models/` (POSIX), overridable via
  `MNEME_MODEL_CACHE`, so OS temp cleanup no longer evicts the
  ~91 MB BGE model; every runtime dependency declares an upper
  bound.
- **Dependency versions pinned.** `sqlite-vec>=0.1.9,<0.2`,
  `fastembed>=0.8.0,<0.9`, `PyYAML>=6.0,<7`, `tomli_w>=1.0,<2`,
  `tomli>=2.0,<3`. Pre-v1 upstream changes can no longer flip
  behavior on a clean install without a Mneme code change.
- **SKILL language-variant drift detection.**
  `tests/test_skill_drift.py` asserts EN and ZH `SKILL*.md`
  advertise the same scenario set (`init` / `reindex` / `search` /
  `ingest` / `query` / `lint`), neither resurrects `dream`, and
  both cite the same OKF version.
- **CI matrix green.** `.github/workflows/ci.yml` runs pytest
  across Python 3.10 / 3.11 / 3.12 / 3.13 × ubuntu-latest /
  macos-latest (8 cells), plus a single-cell wheel-install smoke
  job that proves a fresh-venv `mneme init` + `mneme lint` works
  against the built wheel.

### What 1.0.0 does NOT include

The assessment's "Recommended version path" treated 0.3.0 → 0.4.0
→ 0.5.0 → 0.9.0 → 1.0.0 as a linear sequence; in practice the
project shipped straight through 0.6.1 without a 0.9.0 release
candidate. The release gate is closed by the items above, not by
a separate RC phase. Deferred work tracked in `docs/superpowers/`:

- **Phase 5 dream safety** — `find_orphans` is a library primitive
  (v0.6.0) and wired into `mneme lint` (v0.6.1), but the full
  auto-curation pipeline (similarity merge, archive, cross-link
  suggestions, atomic write protocol + git-safety TDD suite) is
  not implemented. `mneme dream` stays not registered.
- **Real 141-document dogfood** — the v0.5.0 benchmark against
  `/Users/scott1743/Desktop/佳都/飞书文档库/` (Recall@5 = 1.000,
  MRR = 0.800) stands as the labeled retrieval evidence, but the
  corpus is not in the repository; the benchmark test skips on
  machines that do not have that path.
- **Converters (Word / PDF / PPT / Excel / HTML → md/csv)** and
  **MCP server** — still deferred per `AGENTS.md` §非目标.

### Test changes

- `tests/test_version.py` — rewrote from constants-only to two
  real assertions: pyproject `version` == `__version__`, and
  major >= 1 (release gate marker).
- `tests/test_install.py` / `tests/test_entrypoint.py` — wheel
  selection now picks the highest-version wheel in `dist/`, not
  the alphabetically-first. Added `_latest_wheel()` helper.
- `tests/test_e2e_ingest.py` — four tests now pass `--config` to
  `mneme init` so they no longer touch the user's
  `~/.config/mneme/config.toml`.
- `tests/test_release_budget.py` (new) — 5 release-gate budget
  tests.
- `tests/test_skill_drift.py` (new) — 3 EN/ZH drift tests.

## [0.6.1] — 2026-07-12 — hotfix: `mneme lint` calls `find_orphans` for real

`v0.6.0` shipped the `oklib.find_orphans` library primitive but
the `mneme lint` subcommand still printed the v0.3.0 freeze guard
text "`find_orphans not yet implemented`" as if the primitive
were still missing. The library primitive WAS installed; only the
CLI surface wasn't wired. This release is the wire.

### Fix

- `mneme lint <bundle>` now calls `oklib.find_orphans(bundle)` and
  prints the list on stderr as an "orphan concept pages (N)"
  section. The v0.3.0 freeze guard message is removed.
- Exit code semantics unchanged from v0.6.0:
  - `1` = bundle missing or validator found errors
  - `3` = validate clean; orphan section is included

### Test changes

- `tests/test_cli.py::test_cli_lint_runs_find_orphans` — rewrote the
  v0.3.0 freeze test to assert the **real** orphan output plus a
  regression guard that asserts `find_orphans not yet implemented`
  does not reappear in stderr.
- `tests/test_e2e_lint.py::test_clean_bundle_has_no_errors` —
  added `0 warning(s)` + `orphan concept pages (0)` assertions
  and a regression guard for the freeze text.
- `tests/test_entrypoint.py::test_init_then_lint_in_fresh_venv` —
  rc assertion moved from `!= 2` to `== 3` (reflecting the
  status-quo exit code).
- `tests/test_e2e_ingest.py::test_e2e_lint_clean_after_ingest` —
  assertion changed from `find_orphans not yet implemented` to
  `orphan concept pages` plus regression guard.

## [0.6.0] — 2026-07-12 — `find_orphans` primitive (library API)

This release lands **one** library primitive from Phase 5 of the
readiness-assessment plan: `okflib.find_orphans(bundle_path)`. It
is the inverse of OKF §9 ("every concept page is reachable from
`index.md`") — returns the sorted list of concept slugs that no
`.md` file inside the bundle cross-references.

### `find_orphans` (library API)

- **`okflib.find_orphans(bundle_path)`** returns the sorted list
  of concept slugs not referenced from anywhere in the bundle.
  OKF §9 calls this the inverse of "every concept is reachable
  from `index.md`".
- Walks every `.md` file under the bundle, skipping `.mneme/`
  and `sources/`. Captures both `/concepts/foo.md` absolute
  links and `concepts/foo.md` relative links; relative paths
  are treated as bundle-rooted.
- **`list_concepts`** gets a small hygiene fix: now skips
  `sources/` (matching the validator) and uses
  `if not p.is_file(): continue` so a stray `something.md/`
  directory under the bundle can't sneak past `rglob('*.md')`
  on POSIX.

### Not in this release

Phase 5 (per the readiness-assessment §Phase 5) has four parts:

  1. real merge of similar concepts (requires a similarity
     implementation tied to actual sqlite-vec cosine distance)
  2. real archive of stale orphans (90-day threshold)
  3. real cross-link suggestions between siblings
  4. atomic write protocol + manifest preview + git-safety TDD suite

This release delivers only the `find_orphans` *primitive* — the
building block these features would consume. Wiring `find_orphans`
into `mneme lint`, the actual similarity math, and the rest of the
auto-curation pipeline are deferred.

`mneme dream` stays **not registered** (the v0.3.0 freeze removed
it; this release does not re-introduce it). The dream recovery
prerequisites in
`docs/superpowers/plans/2026-07-12-mneme-0.3.0-implementation.md`
§2.3 are intentionally not satisfied in this single-primitive
release.

### Tests

- `tests/test_okflib.py` — 5 new `find_orphans` cases (empty
  bundle / single unreferenced / index-listed / peer-to-peer /
  sources-excluded).
- All 38 existing fast tests + the 5 new ones = 43 fast tests
  in test_okflib.py. 103 fast tests total (full suite).

## [0.5.0] — 2026-07-12 — Phase 4 dogfood on the Feishu 141-doc corpus

The first v0.5.0 release. v0.5.0 is the **dogfood milestone** that
the readiness assessment defines as "real 141-document dogfood and
retrieval benchmark". This release ships the bootstrap tooling, the
labeled benchmark, and a clean pass against both.

### Phase 4 — dogfood on real data

- **`scripts/bootstrap_dogfood.py`** reads a directory of `.md`
  source files and scaffolds a fully-formed OKF bundle — init,
  sources/, concepts/ (one type=Source per source), index.md
  listing every concept under `## Sources`, and log.md with one
  **prepended** ingest event per source. Idempotent and
  parameterless.
- **`tests/test_retrieval_bench.py`** runs the bootstrap +
  reindex in a tmp_path fixture, then queries a hand-picked
  5-query labeled set. Returns:
  ```
  Recall@1: 0.600
  Recall@3: 1.000
  Recall@5: 1.000
  MRR:      0.800
  ```
- Both readiness-provisional gates
  (`Recall@5 ≥ 0.85`, `MRR ≥ 0.70`) are met against the user's
  actual corpus at `/Users/scott1743/Desktop/佳都/飞书文档库/`.
- Full results, ranked expectations, and caveats:
  `docs/superpowers/reports/2026-07-12-mneme-0.5.0-bench-results.md`.

### Bug discovered during dogfood

- **YAML block-scalar hazard**: bootstrap's first generation
  emitted descriptions whose first line started with `>` (folded)
  or `|` (literal); PyYAML interpreted those as block-scalar
  markers and rejected the rest as malformed. Fix: the
  description is now always emitted as an explicit
  double-quoted scalar, with `\\` and `\"` escapes, AND leading
  YAML-significant characters stripped from the source line
  before quoting. After the fix, `mneme lint` on the 142-source
  bundle reports 0 errors / 0 warnings.

### Not yet done

- **Phase 5** — `find_orphans` + safety-tested dream workflow.
  The `mneme lint` command still emits the
  "find_orphans not yet implemented" guard.
- **Phase 6** — release-gate CI matrix (Python 3.10–3.13 ×
  Linux/macOS), dependency pinning for sqlite-vec / fastembed,
  resource budgets.

## [0.4.0] — 2026-07-12 — Phase 3 end-to-end harness complete

Closes the v0.4.0 milestone (Phase 3 of the readiness-assessment
version path). The two pillars this release lands on top of v0.3.0.1:

### Phase 3 — end-to-end harness complete

The host agent drives the user's wiki through three CLI commands
(init / search / lint). v0.4.0 locks in each one behind a scriptable
test so a regression in the CLI surface — not just in the library —
is caught at commit time.

- **`tests/test_e2e_ingest.py`** + **`tests/fixtures/e2e_ingest/source.md`**:
  scripts the SKILL.md §"Scenario: ingest" flow end-to-end in
  tmp_path: copy raw source → decompose → write concept pages →
  prepend log entry → reindex → search finds each concept.
- **`tests/test_e2e_lint.py`** + **`tests/fixtures/e2e_lint/{clean,dirty}_bundle/`**:
  a curated violation map across every PR2 rule (one concept file
  per rule plus illegal extra root-index keys plus out-of-order log
  entries). Pins the rule set, the violation severity, and the
  sources/ raw-input carve-out.
- **`tests/test_e2e_query.py`** + **`tests/fixtures/e2e_query/`**:
  asserts the `mneme search` shell — exit code, JSON-array shape,
  stable hit schema, no-duplicate-concept_ids in top-k, hit path
  resolves to a real Markdown file. Retrieval *quality* (recall@5 /
  MRR@10 over a labeled corpus) stays Phase 4 / v0.5.0 scope.

### Bug discovered + fixed by the ingest harness

- **`okflib.validate_bundle`** was walking every `.md` file under
  the bundle and treating `sources/*.md` as concept pages, so every
  lint reported
  `ERROR  sources/source.md: [no-frontmatter] missing YAML frontmatter
  block`. Raw sources MUST NOT carry OKF frontmatter (they predate
  distillation). Validator now skips `sources/` exactly the way it
  skips `.mneme/`.
- **`tests/test_install.py::test_wheel_install_provides_entry_point`**
  was hardcoded to look for
  `mneme-0.2.1rc1.dist-info/entry_points.txt`. The wheel version
  rolled on, the test silently broke. Now dynamically finds any
  `*entry_points.txt` inside the wheel.

### Release-gate hardened

- **`tests/test_entrypoint.py`** — fresh-venv `mneme --help` smoke
  catches the v0.3.0 entry-point argv bug class permanently. Four
  cases: console script help, `python3 -m mneme` help, end-to-end
  `init → lint`, wheel records entry points.
- **`tests/test_version.py`** — added `0.3.0.1` to the freeze-marker
  set; `0.4.0` lands as a new release but the freeze marker
  semantics carry forward.
- **`docs/superpowers/plans/2026-07-12-mneme-0.3.0-implementation.md`
  §5.1** — points the release-gate contract at `test_entrypoint.py`
  (not just `test_install.py`).

### Housekeeping

- `dist/` cleaned: only the latest wheel ships. Older / buggy wheels
  removed so `pip install dist/mneme-0.*.whl` always lands on the
  intended version.
- `dev/` `mneme.egg-info/` was already covered by `*.egg-info/` in
  `.gitignore`; nothing to do (verified, not changed).

### Not yet done

- Phase 4 — real 141-document dogfood and retrieval benchmark. The
  fixtures in `tests/fixtures/e2e_query/` and `e2e_lint/` are
  synthetic. Phase 4 builds a labeled benchmark over the
  `/Users/scott1743/Desktop/佳都/飞书文档库/` corpus.
- Phase 5 — `find_orphans` + dream safety.
- Phase 6 — release-gate CI matrix + resource budgets.

## [0.3.0.1] — 2026-07-12 — hotfix: console entry point missing argv

## [0.3.0.1] — 2026-07-12 — hotfix: console entry point missing argv

The v0.3.0 wheel installed cleanly but invoking the `mneme` console
script crashed with `TypeError: main() missing 1 required positional
argument: 'argv'` because setuptools' generated entry-point stub calls
`main()` without arguments, while the implementation declared
`def main(argv)`. Same crash for `python3 -m mneme`.

`mneme.cli.main` now defaults `argv=None` and reads from `sys.argv[1:]`
when the entry-point stub invokes it without args; existing tests that
pass an explicit argv list keep working unchanged.

If you installed `mneme==0.3.0` and saw the crash, upgrade:
```
pip install --upgrade mneme==0.3.0.1
```

## [0.3.0] — 2026-07-12 — Phase 2 install/path + dogfood-ready

This release closes out the v0.3.0 milestone:

- **Real Python package.** Implementation lifted from
  `skills/mneme/scripts/` into `src/mneme/` as a true package; the
  legacy `skills/mneme/scripts/` is a symlink for the dev install
  path. `pip install -e .[dev]` or `pip install mneme==0.3.0`
  builds the same layout.
- **`mneme` console command.** `[project.scripts]` exposes
  `mneme = mneme.cli:main`. From a clean venv:
  ```
  $ pip install mneme==0.3.0
  $ mneme --help
  usage: mneme [-h] {init,reindex,search,lint} ...
  ```
- **SKILL assets inside the wheel.** `mneme/skill/SKILL.md`,
  `mneme/skill/SKILL cn.md`, and `mneme/skill/references/*` are
  packaged via `[tool.setuptools.package-data]`. Agent invocations
  now reference `mneme <cmd>` rather than repository-relative
  `python3 skills/mneme/scripts/...` paths.
- **TOML config via stdlib + tomli_w.** `mneme.config.read_config`
  uses `tomllib` on Python 3.11+ (falls back to `tomli` via the
  `toml10` extras on 3.10); `write_config` uses `tomli_w`. The
  hand-rolled `splitlines + split('=', 1)` parser is gone. Round-
  trip preserves embedded quotes, backslashes, and non-ASCII
  characters; tests cover each case.
- **No more `dist/` manual copy.** `python -m build --wheel` is the
  single source of truth. The pre-existing `dist/mneme-0.2.0/` is
  removed.

### Validation under v0.3.0

`mneme lint <bundle>` runs the full PR2 rule table (Phase 1 conformance)
in a single subcommand and surfaces the orphan analysis with a
deterministic "find_orphans not yet implemented" message until that
primitive lands in a future release.

### Step back

This is **not** 1.0.0. v0.3.0 is a real install/QA milestone, but the
`1.0` release gate still requires:

- 141-document dogfooding with a labeled retrieval benchmark (Phase 4)
- `find_orphans` + safety-tested dream (Phase 5)
- resource budgets, dependency pinning, and CI across Python
  3.10–3.13 (Phase 6)

See `docs/superpowers/reports/2026-07-12-mneme-1.0-readiness-assessment.md`
for the full list.

### Phase 1 conformance under v0.3.0

The OKF v0.1 rule table lands in v0.3.0 (rolled forward from 0.2.1rc1):

- **PyYAML verify path** in `okflib._strict_meta()`. Base installs stay
  zero-dep; `pip install 'mneme[validate]'` enables strict YAML
  verification. Without it the validator reports a
  `strict-validation-disabled` warning so callers can see they are in
  fallback mode.
- **Type-field rule table**:
  - missing `type` → `empty-type` error
  - empty/whitespace `type` → `empty-type` error
  - non-scalar `type` (list / int / bool / null) → `type-not-scalar`
    error (was silently coerced to a non-empty string before)
  - unknown `type` (anything outside `Concept` / `Reference` /
    `Summary` / `Source`) → `unknown-type` warning
- **Reserved-file rules (SPEC §6 and §7)**:
  - nested `index.md` with any frontmatter → `nested-index-frontmatter`
    error
  - root `index.md` may declare only `okf_version`; any other key
    → `root-index-extra-key` error
  - root `index.md` missing `okf_version` → `missing-okf-version`
    warning (recommended but not required)
  - `log.md` heading without a `YYYY-MM-DD` date prefix →
    `log-heading-format` error
  - `log.md` entries not in newest-first order →
    `log-not-newest-first` error
  - missing `log.md` → `missing-log` warning (optional per SPEC §7)
- **Timestamp soft tolerance (SPEC §4.1 line 131 + §9 line 354)**:
  - missing `timestamp` → `missing-timestamp` warning
  - empty `timestamp` → `empty-timestamp` warning
  - non-ISO-8601 `timestamp` → `bad-timestamp-format` warning
- **Tolerance for unknown frontmatter keys** (`unknown-key` warning) and
  for one bad file not hiding valid concepts elsewhere
  (`test_isolation_invalid_file_does_not_hide_valid_concepts`).

40 OKF conformance tests in `tests/test_okflib.py` (16 → 40). 91 total
tests pass at v0.3.0 (was 72 after PR2; +19 for install/path coverage).

## [0.2.1rc1] — 2026-07-12 — freeze dangerous behavior

This is a **freeze pre-release**, not a feature release. It explicitly
removes or guards every behavior flagged P0/P1 in the v0.2.0 readiness
assessment at `docs/superpowers/reports/2026-07-12-mneme-1.0-readiness-assessment.md`.
The version is bumped from `0.2.0` → `0.2.1rc1` so accidental `pip
install mneme` does not pick up dangerous code paths by default.

### Removed (gone, see notes for re-introduction)

- **`mneme dream` scenario and prose-defined auto-curation pipeline.**
  The dream workflow described in v0.2.0's SKILL.md used a similarity
  threshold that did not match sqlite-vec's actual distance metric,
  called a non-existent `okflib.find_orphans()` primitive, and ran
  `git add -A` before resolving the bundle — any of which is a
  merge-blocking defect on its own. The scenario is removed from both
  English and Chinese SKILL.md; a note replaces it citing the
  recovery prerequisites.

### Now explicit and deterministic

- **`mneme lint <bundle>` is now a real subcommand.** Previously
  undocumented in the CLI dispatcher, the command now delegates to
  `validate_okf.py` and emits a deterministic "find_orphans not yet
  implemented" message instead of an opaque `AttributeError`. Exit
  code 3 distinguishes guard-fired from argparse's exit code 2.
- **Ingest scenario redirects the host agent to copy the raw source**
  into `<bundle>/sources/<basename>` **before** distillation, matching
  the OKF v0.1 immutable-source contract.
- **Ingest scenario prepends the new `log.md` entry at the top**, not
  appends. OKF §6 requires newest-first; appending for months produces
  an oldest-first log.
- **`SKILL.md` no longer mentions a fake-embed production fallback.**
  v0.2.0's English SKILL left a "Only acceptable for tests" escape
  hatch; both language variants now tell the host agent to surface
  the model load failure and require `pip install 'mneme[index]'`.

### Documentation cleanup

- **`CLAUDE.md` no longer references the v2.1-deleted Strands agent
  layer.** The "L3 Strands agent (ingest/query/lint)" bullet is gone;
  the directory tree no longer lists `tools.py`/`ingest.py`/`query.py`/
  `lint.py` (none of which exist after the v2.1 thin-CLI refactor);
  the CLI is correctly described as argparse, not "Click 风格".
- **`AGENTS.md` is unchanged.** It already reflects the v2.1+ reality.

### Not yet addressed (deferred per scope, tracked in `docs/superpowers/`)

- Phase 1 OKF conformance TDD — covered by
  `docs/superpowers/plans/2026-07-12-mneme-0.3.0-implementation.md` §4.
- Phase 2 install/path TDD (proper `mneme` wheel) — same plan, §5.
- Real 141-document dogfood and retrieval benchmark — 0.5.0.
- Re-introduction of dream — only after Phase 5 retrieval benchmark
  passes, `find_orphans` + similarity-safe workflow under test, and
  dry-run preview mode + a dedicated safety TDD suite.

## [0.2.0] — 2026-07-11 — search CLI

Added `mneme search <query>` (KNN over the L2 sqlite-vec index), atomic
reindex, BGE/small/zh-v1.5 default model, deterministic test fakes.

## [0.1.x and earlier]

See `git log` for v2.1, v2, v1 and prior history. The skill-first
install path is documented at the project README.
