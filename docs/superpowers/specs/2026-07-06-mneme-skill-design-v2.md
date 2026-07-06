# Mneme Skill — Design Spec v2

- **Date:** 2026-07-06
- **Status:** Draft — awaiting user review
- **Supersedes:** `2026-07-06-mneme-skill-design.md` (v1) — v1 hand-waved scale/retrieval/orchestration; v2 adds the L2 index + L3 engine layers.
- **Research basis:** gbrain（本机 gstack brain：PGLite/Supabase + pgvector + MCP 的本地参考实现）、Strands Agents SDK（`strands-agents/harness-sdk`，Apache-2.0，agent harness）。

## 1. 目标与身份

mneme 是一个**轻量化、本地优先**的 LLM wiki，以 agent skill 为载体，继承 Karpathy *LLM Wiki* 思想、服从 OKF v0.1。

**轻量化理念（本次明确）**：嵌入式存储（sqlite-vec）、按需执行（无常驻服务）、CLI 通用链入（不做 MCP）。能力靠分层提供——轻量承诺只约束 L1 wiki 层，engine 层（L2/L3）按需启用。

## 2. 关键决策

| # | 决策点 | 选择 |
|---|---|---|
| D1 | wiki 位置 | 外部 bundle + 便携 skill（真 wiki 在仓库外） |
| D2 | 内容域 | 研究/学习笔记；type: Concept/Reference/Summary/Source |
| D3 | 分层 | L1 wiki + L2 index + L3 engine + L4 skill |
| D4 | 位置持久化 | `~/.config/mneme/config.toml` + 用户级 skill |
| D5 | L2 索引 | **sqlite-vec**（嵌入式），向量存 `<bundle>/.mneme/index.db` |
| D6 | embedding 生成 | **本地 fastembed (ONNX)**，多语种小模型（如 `bge-small-zh-v1.5` / `multilingual-e5-small`），离线、China 网络安全 |
| D7 | L3 engine | **Strands agent**（ingest/query/lint），按需 invoked、无常驻服务；agent loop 给脚本提供多元化工具，不是为用而用 |
| D8 | 链入智能体 | **CLI 默认**（通用）+ skill（Claude Code）。MCP 不做——CLI+skill 已覆盖 |

## 3. 分层架构

| 层 | 是什么 | 解决 | 依赖 |
|---|---|---|---|
| **L1 Wiki** | OKF bundle（本地 .md + frontmatter，source of truth，可 git） | 轻量、可移植、不锁死 | stdlib（okflib） |
| **L2 Index** | sqlite-vec 向量索引，ingest 时增量更新 | **context overflow**——agent 检索 top-k 片段而非全量 | sqlite-vec + fastembed |
| **L3 Engine** | Strands agent（ingest/query/lint），按需脚本，带工具集 | **agent 中间处理** + 可复现/可脚本化 | strands-agents |
| **L4 Skill** | SKILL.md 薄编排，调 CLI | Claude Code 原生 UX | — |

**与 gbrain 的同构**：gbrain 的 brain（DB+embedding）= mneme 的 L2；gbrain 的源文件 = mneme 的 L1 wiki。mneme 多一步把 wiki 显式做成 OKF（人/agent 都可读的 source of truth，可 git）。**与 v1 的关系**：v1 的 okflib/校验器/SKILL.md 进 L1+L4，不白做。

## 4. L1 — Wiki 结构 spec

growth 要有去处。一个 bundle：

```
<bundle>/
├── index.md          # 根索引（渐进式展开入口；root 带 okf_version）
├── log.md            # 变更时间线（## YYYY-MM-DD <op> | <title>）
├── sources/          # 不可变原始源副本（ingest 时复制进来）
├── concepts/         # 原子概念页（主体，扁平 + slug）
├── references/       # 蒸馏的外部源（论文/文章）
├── summaries/        # 跨概念综合（compaction 产物）
├── topics/           # 主题枢纽（策展阅读路径/地图）
├── archive/          # 过时页（保留历史，退出索引）
└── .mneme/           # 派生层（L2 索引，gitignore，不入 OKF）
    └── index.db
```

**规整机制**：一概念一页；slug 规则（小写、空格→连字符）；交叉链接用绝对 bundle-relative（`/concepts/x.md`）；达阈值时 `summaries/` 滚动压缩多页为一篇；`archive/` 退役过时页（退出 L2 索引、保留历史）；`topics/` 提供策展入口。检索靠 L2，文件树可扁平，不必手工深嵌套。`.mneme/` 是派生层，不进 OKF 概念集，校验器跳过。

## 5. L2 — Index 设计（sqlite-vec + fastembed）

- **存储**：`<bundle>/.mneme/index.db`（SQLite + sqlite-vec 扩展）。gitignore。随 wiki 走。
- **schema**：
  - `chunks(id, concept_id, path, title, type, chunk_idx, text, tags, timestamp, embedding)`——`embedding` 为 sqlite-vec 向量列。
  - `sources(id, slug, path, hash, indexed_at)`。
  - `meta(key, value)`——`embedding_model`、`dim`、`okf_version`、`last_sync`。
- **embedding**：fastembed，多语种小模型（`bge-small-zh-v1.5` 512-dim 或 `multilingual-e5-small` 384-dim，记入 meta）。离线，无 key。
- **chunking**：概念页按 markdown 标题分节，每节一块；源按段落/定长（~512 token，overlap 64）。
- **增量**：ingest 时按 hash 判变；未变跳过，已变重嵌受影响块。mtime/hash 快路径（gbrain 式）。
- **查询**：embed 问题 → sqlite-vec KNN top-k → 取块文本 + concept_id → 返回排好序的片段与概念路径。

## 6. L3 — Engine（Strands agent，按需）

三个 Strands agent，各带工具集，**按需脚本 invoked，不启 daemon**。agent 自己决定拆解/综合策略（中间过程 agent 处理）：

- **ingest.py**：工具 `read_source / chunk / embed_and_upsert / write_concept / update_index_md / cross_link / append_log / validate / list_concepts / read_concept`。给定源路径，读 → 决定概念分解 → 写页 → 交叉链接 → 入索引 → 校验。
- **query.py**：工具 `embed_query / search_index / read_concept / read_chunk`。embed 问题 → top-k 检索 → 读片段 → 带引用综合。
- **lint.py**：工具 `validate / list_concepts / search_index / find_orphans / find_stale / read_concept`。跑校验器 + 索引健康（孤儿页、过时、断链）→ 提改、经同意后修。

**模型 provider**：Strands agent 需一个 LLM 驱动 loop。默认 Anthropic（复用用户的 Claude API key），Ollama 作为离线/本地方案。配置项 `MNEME_MODEL_PROVIDER`。

## 7. 链入智能体（D8）——同一份 engine，两个调用面

1. **CLI `mneme`**（默认、通用）：`mneme ingest <src>` / `mneme query <q>` / `mneme lint` / `mneme init <path>`。任何 agent/宿主走 bash。**无常驻服务**。
2. **Skill `SKILL.md`**（Claude Code 原生）：description 触发，内部调 CLI。

一套代码，两个调用面。MCP 不做（CLI+skill 已覆盖）；若未来多 agent 共享需求出现再加（见 §15）。

## 8. Bundle 解析（Step 0，每次必跑）

`~/.config/mneme/config.toml` `bundle_path` → `MNEME_BUNDLE` → 显式 arg → 自动发现（root `index.md` 含 `okf_version`）→ `./wiki` → 提示 init。索引恒在 `<bundle>/.mneme/index.db`。

## 9. 数据流

- **ingest <src>**：解析 bundle → 复制源到 `sources/` → Strands ingest agent 跑（读源→分解→写概念页→交叉链接→入 L2 索引→更新 index.md/log.md→validate）。中等规模下 agent 一次跑完；大源由 Strands 自带 context management 分段。
- **query <q>**：解析 bundle → Strands query agent（embed→top-k→读→带引用综合）→ 若答案广泛有用且无页，提议回填（不自动）。
- **lint**：解析 bundle → Strands lint agent（validate + 索引健康）→ 提改、经同意修。
- **init <path>**：脚手架空 bundle + 写 config。

## 10. 错误处理

- bundle 找不到 → 提示设 config 或 init。
- L2 索引缺失 → ingest/query 自动建/重建（首次或 `mneme lint --reindex`）。
- embedding 模型未装 → 明确报错 + 安装提示（`pip install 'mneme[index]'`）。
- Strands model provider 未配 → 报错 + 配置提示。
- 断链 → 非错误（OKF 容错），lint 软告警。

## 11. 测试（TDD）

- L1：okflib 测试（v1 既有，14 个，保留）。
- L2：indexlib 测试——upsert/查改/增量（hash 跳过）/KNN top-k/模型 dim 一致。
- L3：tools 测试（mock model）+ CLI 烟测（ingest 一个小源 → 校验过 + 索引可查）。
- 流程：失败测试 → 实现 → 绿 → 重构。

## 12. 仓库布局

```
mneme/
├── CLAUDE.md / LICENSE / README.md / pyproject.toml / .gitignore
├── skills/mneme/
│   ├── SKILL.md                       # L4（修订）
│   ├── scripts/
│   │   ├── okflib.py                  # L1（v1 保留）
│   │   ├── validate_okf.py            # L1（v1 保留）
│   │   ├── indexlib.py                # L2（新）
│   │   ├── tools.py                   # L3 共享工具（新）
│   │   ├── ingest.py / query.py / lint.py  # L3 Strands agent（新）
│   │   └── mneme.py                   # CLI 入口（新）
│   └── references/
│       ├── workflow-{ingest,query,lint}.md  # 修订
│       ├── type-vocab.md
│       ├── wiki-structure.md          # L1 结构 spec（新）
│       └── index-design.md            # L2 设计（新）
├── sample-bundle/  tests/  .research/  docs/superpowers/
```

**依赖隔离**（pip extras，base 保持零运行时依赖）：`mneme[index]`（sqlite-vec+fastembed）、`mneme[agents]`（strands）、`mneme[all]`（=index+agents）。

## 13. 非目标（v1 of v2）

- 不启常驻服务（engine 按需脚本；MCP 可选且本机 stdio）。
- 不做远程/云索引（本地 sqlite-vec only）。
- 不做多 bundle 管理。
- 不做 PDF/Office/URL ingest（v2 converters，仍 deferred——见 v1 plan Phase 2）。
- query 回填仅提议。

## 14. 从 v1 迁移

保留：`okflib.py`、`validate_okf.py`、`SKILL.md`（修订）、`references/workflow-*.md`（修订）、`type-vocab.md`、`sample-bundle/`、`tests/`（L1 部分）。新增：`indexlib.py`、`tools.py`、`ingest/query/lint.py`、`mneme.py`、`serve.py`、`wiki-structure.md`、`index-design.md`。v1 的"index.md 渐进式展开足够"论断作废——L2 接管规模化检索。

## 15. 未来

- **v2 converters**（Word/PDF/PPT/Excel/图片/HTML→md/csv）：v1 plan Phase 2，仍 deferred。
- **MCP server**（`mneme serve`）：CLI+skill 已覆盖链入；若未来要一等工具/跨 agent 共享，再加本机 stdio MCP，wrap 同一份 okflib+indexlib。
- **OKF 扩展提案**：i18n / 代码支持 / HTML 一等公民（向后兼容）。
- **远程索引**：若多机共享需求出现，加 Supabase/pgvector 后端（gbrain Path 1/4 同款），本地优先不变。
