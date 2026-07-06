# Mneme — 轻量化 LLM Wiki

> Mneme（摩涅墨叙涅），希腊神话中的记忆女神。本项目是一座**生于本地文件系统、由 agent 增量维护**的轻量 LLM 知识 wiki。

## 这是什么

Mneme 是一个以 **agent skill 为载体**的轻量化 LLM wiki。它：

- **继承** Andrej Karpathy 的 *LLM Wiki* 思想（2026-04-04 gist）——把知识当代码编译一次、持续复利，而非每次提问重新 RAG；
- **服从** Google 发布的 **OKF (Open Knowledge Format) v0.1** 协议（2026-06-12，MIT）——一个目录的 Markdown + YAML frontmatter，3 条规则，无运行时；
- **载体**是一个 Claude Code agent skill——`SKILL.md` 教会 agent 像维护源码一样 ingest / query / lint 一座 OKF 合规的 wiki。

一句话：**让 agent 在一个本地 Markdown 目录上，增量地编译、查询、体检一座 OKF 合规的知识 wiki。**

## 思想谱系

```
Karpathy LLM Wiki (2026-04-04 gist)
        │  “Obsidian 是 IDE；LLM 是程序员；wiki 是代码库。”
        │  三层架构 + ingest/query/lint + index.md/log.md
        ▼
各团队各自实现（AGENTS.md / CLAUDE.md / Obsidian vault / index.md+log.md）
        │  一百种互不兼容的重复造轮
        ▼
Google 标准化为 OKF v0.1 (2026-06-12)  ← 把 Karpathy 的“个人约定”补上“跨生产者/消费者互通”的契约
        │
        ▼
Mneme：把 OKF 落成一个本地优先、零依赖的 agent skill
```

详见 [`.research/design-rationale.md`](.research/design-rationale.md)。

## 三层架构（继承自 Karpathy）

| 层 | 角色 | 谁拥有 | 在 mneme 中的位置 |
|---|---|---|---|
| **Raw sources** | 原始资料，事实来源 | 不可变，LLM 只读不改 | `wiki/sources/`（或外部路径引用） |
| **The wiki** | 互链的 Markdown 概念页 | LLM 完全拥有并维护 | `wiki/` —— OKF bundle 本体 |
| **The schema** | 告诉 LLM “wiki 怎么组织、工作流怎么走” | 人 + LLM 共同维护 | **本 `CLAUDE.md`** + `SKILL.md` |

> 本文件即 Karpathy 三层架构中的 **schema 层**：它让 agent 成为有纪律的 wiki 维护者，而非泛泛的聊天机器人。

## 三种操作

- **Ingest（摄入）**：丢一个新源进来 → agent 读它、讨论要点、写摘要页、更新 `index.md`、更新相关概念页、往 `log.md` 追加一条。一个源可能动 10–15 个页面。
- **Query（查询）**：对 wiki 提问 → agent 先读 `index.md` 定位、再钻相关页、带引用综合作答。好答案可回填成新页面，让探索也复利。
- **Lint（体检）**：定期健康检查 → 找矛盾、过时论断、孤儿页、缺页的重要概念、缺失的交叉引用。

## OKF 合规约束（硬约束）

一个 bundle **符合 OKF v0.1** 当且仅当（SPEC §9）：

1. 树中每个**非保留**的 `.md` 文件都含可解析的 YAML frontmatter 块。
2. 每个 frontmatter 块都含**非空 `type` 字段**（唯一必填字段）。
3. 保留文件名 `index.md` / `log.md` 出现时，分别遵循 §6 / §7 的结构。

**frontmatter schema**（SPEC §4.1）：

```yaml
---
type: <Type name>            # REQUIRED。短字符串，消费者据之路由/过滤。值不集中注册。
title: <display name>        # recommended
description: <one-line>      # recommended
resource: <canonical URI>    # recommended，抽象概念可省
tags: [<tag>, ...]           # recommended
timestamp: <ISO 8601>        # recommended，最后修改时间
okf_version: "0.1"           # 仅 bundle 根 index.md 可带，声明目标版本
---
```

**保留文件**：`index.md`（目录索引，支持渐进式展开，无 frontmatter；仅 bundle 根可带 `okf_version`）；`log.md`（日期前缀的时间线，newest-first）。

**链接**：概念间用标准 Markdown 链接。**绝对 bundle-relative 形式**（以 `/` 开头，如 `/tables/customers.md`）为推荐形式——文件在子目录内移动时仍稳定。

**容错消费契约（SPEC §9，必须遵守）**：消费者**不得**因以下任一情况拒绝一个 bundle：缺失可选 frontmatter 字段、未知 `type` 值、未知额外 frontmatter 键、断链、缺 `index.md`。一个文件不合规不得影响其他文件可用性。

> 完整规范原文（MIT，verbatim）见 [`.research/upstream/OKF-SPEC.md`](.research/upstream/OKF-SPEC.md)。蒸馏后的硬规则见 [`.research/constraints.md`](.research/constraints.md)。

## 项目硬约束

- **仅本地文件系统**：无数据库、无服务端、无 SDK、无云、无构建步骤。能 `cat` 就能读，能 `git clone` 就能 ship。
- **载体是 agent skill**：遵循 Claude Code skill 格式（`SKILL.md` + YAML frontmatter：`name` / `description` / `allowed-tools` 等，可附 `references/` 支撑文档与 `scripts/` 零依赖脚本）。
- **轻量优先**：3 条规则，不是 300 条。中等规模（~100 源、数百页）下 `index.md` 的渐进式展开即可免掉 embedding/RAG 基建。
- **git-native**：bundle 即仓库/目录，知识像代码一样 diff / branch / review / blame。
- **零第三方依赖**：任何脚本只用标准库；产物须通过 OKF 一致性校验。
- **最小意见、自由扩展**：只标准化自描述所需的最小结构集；其余留给生产者。frontmatter 可带任意额外键，消费者须保留未知键。

## 目录结构

```
mneme/
├── CLAUDE.md              # 本文件 = schema 层（项目宪法 + agent 维护规约）
├── SKILL.md               # agent skill 载体：ingest / query / lint / init
├── scripts/
│   ├── okflib.py          # 零依赖 OKF 库（parse/list/validate；MCP 预留接口）
│   └── validate_okf.py    # okflib 的 CLI 前端
├── references/            # skill 支撑文档（工作流详述、type 词表）
├── sample-bundle/         # 合规示范/测试夹具（非真 wiki）
├── tests/                 # okflib TDD 测试 + fixtures/
├── .research/             # 立项研究档案（upstream/ 为 verbatim MIT 副本，勿改）
└── .gitignore
```

**真 wiki bundle 在仓库外**，路径由 `~/.config/mneme/config.toml` 的 `bundle_path` 指定（见 spec §5 解析顺序）。`sample-bundle/` 仅作测试夹具与格式演示。skill 用户级安装（`~/.claude/skills/mneme` 符号链接到本仓库）后，其 `description` 常驻每会话上下文，跨项目/会话自动触发。

## 在本仓库工作的约定

1. **先读 `.research/`**。任何修改 OKF 合规性的决定，必须能在 `.research/upstream/OKF-SPEC.md` 中找到依据；拿不准时回原文，不要凭记忆改约束。
2. **`upstream/` 目录只读**。其中的文件是上游规范的 verbatim 副本（MIT），**禁止**给它们加 frontmatter 或改动正文——那会破坏“权威参考副本”的语义。要扩展规范，写提案放 `references/`，并标注“向后兼容、不动任何 MUST”。
3. **保持容错消费契约**。写消费者/校验器时，对缺失可选字段、未知 `type`、断链等只告警不拒绝。
4. **概念 ID = 文件路径去 `.md`**。不需要额外 ID 系统。移动文件即改 ID，需同步更新引用。
5. **链接用绝对 bundle-relative 形式**（`/tables/customers.md`），除非确需相对链接。
6. **每次 ingest 都更新 `index.md` 与 `log.md`**。`log.md` 条目用一致前缀（如 `## 2026-07-06 ingest | <标题>`），使其可被 unix 工具解析：`grep "^## " log.md | tail -5`。
7. **图片不是一等公民**。OKF/Mneme 中图里的知识必须先抽成文字才能被 agent 用上（Karpathy 原文提醒：LLM 无法在一次读取里原生读懂含内嵌图片的 Markdown）。
8. **网络受限环境**。本机在中国大陆，WebSearch 不可用，Wikipedia/DuckDuckGo 受 DNS 污染；做调研走 Bing（`www.bing.com/search`）+ GitHub raw/API，或让用户用 `! <cmd>` 在会话内执行需要代理的命令。

## 非目标

- 不定义固定的概念类型 taxonomy（`type` 值不集中注册）。
- 不规定存储 / 服务 / 查询基础设施。
- 不替代领域 schema（Avro / Protobuf / OpenAPI）——OKF 引用它们，不吞并它们。
- 不做 embedding / 向量 RAG 基建（中等规模下 `index.md` 足够；如需检索，外挂如 `qmd` 这类本地工具）。
- 不绑定任何云服务、模型厂商或 agent 框架。

## 下一步

1. 实现 `SKILL.md`：定义 ingest / query / lint 三工作流，约束 agent 产出 OKF 合规 bundle。
2. 写 `scripts/validate_okf.py`：零依赖校验 3 条合规规则（frontmatter 可解析、`type` 非空、保留文件结构）。
3. 初始化 `wiki/` bundle：根 `index.md`（带 `okf_version: "0.1"`）+ `log.md` + 首批概念页。
4. dogfood：把 `.research/` 本身也视作一个 OKF bundle 来审视（参考 awesome-okf 的 dogfooding 做法）。

---

*本项目立项于 2026-07-06。研究资料采集方法见 [`.research/README.md`](.research/README.md)。*
