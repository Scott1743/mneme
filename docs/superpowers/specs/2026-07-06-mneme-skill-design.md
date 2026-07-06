# Mneme Skill — Design Spec

- **Date:** 2026-07-06
- **Status:** Draft — awaiting user review
- **Supersedes:** `CLAUDE.md` 目录布局（实施阶段同步更新）

## 1. 目标与身份

mneme 是一个**轻量化、本地优先**的 LLM wiki，以 **agent skill 为载体**。它：

- 继承 Andrej Karpathy 的 *LLM Wiki* 思想——把知识编译一次、复利维护，而非每次提问重新 RAG；
- 服从 Google **OKF v0.1** 协议——3 条合规规则，无运行时，能 `cat` 就能读；
- 服务于**研究/学习笔记**内容域——论文/文章/概念的蒸馏与互链。

它是 Karpathy 三层架构中的 **schema 层**：用三个工作流（ingest/query/lint）+ 一个零依赖校验器，把 agent 训成有纪律的 wiki 维护者，而非泛泛的聊天机器人。

## 2. 关键决策（brainstorming 结论）

| # | 决策点 | 选择 |
|---|---|---|
| D1 | wiki 位置 | **外部 bundle + 便携 skill**：真 wiki 在仓库外（如 `~/.mneme/wiki` 或独立 repo），mneme 仓库只放 skill + 研究资料 |
| D2 | 内容域 | **研究/学习笔记**（Karpathy 原味）；type 词表 `Concept` / `Reference` / `Summary` / `Source` |
| D3 | 架构 | **单 skill 三模式 + 校验器**：一个 `SKILL.md`（ingest/query/lint）+ 零依赖 validator + `references/` |
| D4 | 位置持久化 | **配置文件 + 用户级 skill 为主，MCP 预留接口**：`~/.config/mneme/config.toml` 存 `bundle_path`；skill 用户级安装；`okflib` 作为未来 MCP server 的可导入前端 |

## 3. 架构

### 三层映射（Karpathy）

| 层 | 在 mneme 中 | 谁拥有 |
|---|---|---|
| Raw sources（不可变） | bundle 内 `sources/`（ingest 时复制的原始 .md/.txt） | 只读 |
| The wiki | OKF bundle：概念页 + `index.md` + `log.md` | LLM 维护 |
| The schema | `SKILL.md` + `CLAUDE.md` | 人 + LLM |

### 存储访问层（MCP 预留接口）

所有与存储的交互走一个**固定的小接口**。v1 由 agent 直接读写文件实现（OKF 哲学：无 adapter）；未来 MCP server 实现同一接口，工作流散文不变：

- `resolve_bundle() -> path`
- `read_index(path)` / `read_concept(id)` / `list_concepts(path)`
- `write_concept(id, frontmatter, body)`（写前校验）
- `append_log(entry)` / `update_index()`
- `validate(path) -> Report`

v1 的代码化身是 `scripts/okflib.py`（可导入的零依赖函数库）；`scripts/validate_okf.py` 是其 CLI 前端。未来 `mneme-mcp` server 导入 `okflib`、把这些函数暴露为 MCP 工具——**只换存储前端，工作流不变**。

## 4. 组件

1. **`SKILL.md`** — 载体。frontmatter（`name: mneme`、`description`[触发词]、`allowed-tools`）+ Step 0 bundle 解析 + ingest/query/lint 三工作流 + OKF 3 规则内联 + type 词表。
2. **`scripts/okflib.py`** — 零依赖（仅标准库）可导入库：frontmatter 解析、concept 列举/读取、bundle 校验。结构为可被未来 MCP server 导入。
3. **`scripts/validate_okf.py`** — `okflib` 的 CLI 前端；硬违规非零退出，软告警只打印。
4. **`references/`** — `workflow-ingest.md`、`workflow-query.md`、`workflow-lint.md`、`type-vocab.md`。
5. **`sample-bundle/`** — 合规示范/测试 bundle（含 `okf_version`、`index.md`、`log.md`、`sources/`、2–3 概念页）。**非真 wiki**，仅作校验器夹具 + 格式演示。
6. **`tests/`** — `okflib` 的 TDD 测试 + `fixtures/` 违规夹具。
7. **`CLAUDE.md`**（更新）— 外部 bundle 模型、新布局、config 解析说明。

## 5. Bundle 解析（Step 0，每次操作必跑）

顺序（先命中先用）：

1. `~/.config/mneme/config.toml` 的 `bundle_path`——**主**，持久的"约定"。
2. `MNEME_BUNDLE` 环境变量。
3. 用户当次显式路径。
4. 自动发现：从 cwd 向上找根 `index.md` 含 `okf_version`（OKF 规定的 bundle 根声明）。
5. 兜底 `./wiki`（若存在）。
6. 都没有 → 提示设 config 或 init。

**init**（轻量第 4 操作）：脚手架空 bundle（根 `index.md` 带 `okf_version: "0.1"` + 空 `log.md` + `sources/`），并把路径写入 `~/.config/mneme/config.toml`。

`config.toml` 最小格式（唯一必填键 `bundle_path`；其余为生产者自定义键，消费者保留）：

```toml
bundle_path = "/Users/scott/mneme-wiki"
# 可选扩展：
# default_type = "Concept"
# author = "scott"
```

**为何能跨上下文丢失**：config 文件持久在盘上；skill 装在用户级（`description` 每会话进上下文 → 跨会话/项目自动触发）；Step 0 永远先读 config。三者合力，agent 无需任何先前会话上下文即可定位 wiki。

## 6. 数据流

### Ingest(源路径)
解析 bundle → 读源（.md/.txt）→ 复制到 `sources/<slug>.md`（不可变 raw 层，bundle 自包含、可 git）→ agent 读源、（可选）与用户讨论要点 → 写概念页（frontmatter: `type`/`title`/`description`/`tags`/`timestamp`/`resource`）+ 更新相关页交叉链接 + 更新 `index.md`（带 description）+ 追加 `log.md`（`## YYYY-MM-DD ingest | <标题>`）→ 跑 `validate`、修硬违规。

### Query(问题)
解析 bundle → 读 `index.md`（渐进式展开）定位相关页 → 读那些页 → **带引用**综合作答（引用 = bundle-relative 概念页链接 + 外部 citations）→ 若答案广泛有用且无对应页，**提议**回填为新概念页（v1 只提议不自动写）。

### Lint()
解析 bundle → 跑 `validate`（硬错误 + 软告警）→ agent 审软告警（矛盾/过时/孤儿页/缺交叉链接/缺重要概念）→ 提改、经用户同意后修。

## 7. 错误处理

- bundle 找不到 → 明确提示设 config 或 init。
- 源不可读 → 报告、跳过。
- ingest 后校验器硬失败 → ingest 视为未完成，必先修（工作流强制合规）。
- 断链 → **非错误**（OKF 容错契约），lint 作软告警。

## 8. 测试（TDD）

`okflib` 是唯一可单测的代码，按 superpowers TDD 建：

- 合法 bundle 通过；缺 frontmatter 失败；`type` 空失败；`index.md`/`log.md` 结构错失败；未知 `type` 通过；断链通过（软告警）；未知额外键通过。
- 流程：先写失败测试 → 实现 → 绿 → 重构。
- ingest/query/lint 是 agent 行为（散文），靠 `SKILL.md` 指令约束，不单测。

## 9. type 词表（推荐非注册）

`Concept`（概念/主题）/ `Reference`（蒸馏的外部源）/ `Summary`（多概念综合）/ `Source`（raw 源文档）。开放扩展，消费者容忍未知值。

## 10. 仓库布局

```
mneme/
├── CLAUDE.md              # 更新：外部 bundle 模型 + 新布局
├── SKILL.md               # 载体：三工作流 + 合规规则 + bundle 解析
├── scripts/
│   ├── okflib.py          # 零依赖可导入库（MCP 预留接口的代码化身）
│   └── validate_okf.py    # okflib 的 CLI 前端
├── references/
│   ├── workflow-ingest.md
│   ├── workflow-query.md
│   ├── workflow-lint.md
│   └── type-vocab.md
├── sample-bundle/         # 测试夹具 + 格式演示（非真 wiki）
│   ├── index.md           # okf_version: "0.1"
│   ├── log.md
│   ├── sources/
│   └── <concept>.md
├── tests/
│   ├── test_okflib.py
│   └── fixtures/          # invalid-* 违规夹具
├── .research/             # （已有）研究档案
└── .gitignore
```

## 11. 安装与激活

- **用户级 skill**：开发期 skill 在本仓库；激活时符号链接 `~/.claude/skills/mneme -> /path/to/mneme`（或复制），使其 `description` 常驻每会话上下文，跨项目/会话自动触发。
- **首次约定位置**：`mneme init` 或首次使用时 skill 提示用户给定 `bundle_path`，写入 `~/.config/mneme/config.toml`。
- **可选加固**：在用户全局 `~/.claude/CLAUDE.md` 加一行指针 "mneme wiki: 见 ~/.config/mneme/config.toml"，让 agent 连触发都不用猜。

## 12. 非目标（v1）

- 不做 URL/web 抓取（中国网络 + 零依赖）。仅本地 .md/.txt。
- 不做 PDF/图片解析（零依赖；图片非一等公民）。
- 不做 embedding/向量 RAG（`index.md` 渐进式展开足够）。
- 不做程序化 ingest 管道（agent 读源写概念，Karpathy 式）。
- 不做多 bundle 管理（一次一个）。
- query 回填仅提议、不自动。
- **不实现 MCP server**（仅预留 `okflib` 接口）。

## 13. 未来演进

- **MCP server**（`mneme-mcp`）：当出现①跨客户端共享 KB 工具、②服务端强制写入合规、③多 agent 规模化 RAG 之任一真实需求时实现；导入 `okflib`，暴露同名工具，工作流不变。
- **OKF 扩展提案**：采纳 awesome-okf 的 i18n（`lang`+`canonical`）、代码支持、HTML 一等公民三份提案（向后兼容，不动任何 MUST）。
