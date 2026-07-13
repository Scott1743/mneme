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
各团队各自实现（AGENTS.md / AGENTS.md / Obsidian vault / index.md+log.md）
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
| **The schema** | 告诉 LLM “wiki 怎么组织、工作流怎么走” | 人 + LLM 共同维护 | **本 `AGENTS.md`** + `SKILL.md` |

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
- **载体是 agent skill**：遵循 Claude Code skill 格式（`SKILL.md` + YAML frontmatter：`name` / `description` / `allowed-tools` 等，可附 `references/` 支撑文档与 `scripts/` 脚本）。
- **轻量优先**：3 条规则，不是 300 条。L1 wiki 层零依赖、可移植；超过 ~100 源 / 数百页后由 L2 索引（sqlite-vec + fastembed）接管检索。
- **git-native**：bundle 即仓库/目录，知识像代码一样 diff / branch / review / blame。
- **分层依赖**：L1（OKF bundle + okflib）保持 stdlib 零依赖。L2 检索（sqlite-vec + fastembed）是 opt-in：用户用 L2 时自行 `pip install` 那两个包。skill 不自带任何 pip 安装。
- **按需、无常驻服务**：宿主 agent 按 `SKILL.md` 执行 ingest/query/lint/dream；CLI 只承载确定性的 `init` / `reindex` / `search`。MCP 暂不实现。
- **最小意见、自由扩展**：只标准化自描述所需的最小结构集；其余留给生产者。frontmatter 可带任意额外键，消费者须保留未知键。

## 目录结构

工程过程与最终 skill 交付物分离（skill 开源最佳实践）。**v1.1.0 起唯一交付物是 skill 目录本身**——没有 wheel、没有 `src/`、没有 `dist/`：

```
mneme/                              # 仓库根（开发/测试；非交付物）
├── AGENTS.md                       # schema 层（项目宪法 + agent 维护规约）
├── pyproject.toml                  # 仅 [tool.pytest] 配置；无 [project]，无 wheel
├── .gitignore
├── skills/
│   └── mneme/                      # ← 唯一交付物（打成 dist/mneme-*.zip）
│       ├── SKILL.md                #   英文版（权威；v1.1.0 起单一交付）
│       ├── scripts/
│       │   ├── mneme.py            #   CLI 入口 shim（python3 mneme.py <subcmd>）
│       │   └── mneme/              #   Python 包（cd scripts && python3 -m mneme ...）
│       │       ├── __init__.py     #   __version__ = "1.1.0"；导出 main
│       │       ├── __main__.py     #   `python3 -m mneme` 入口
│       │       ├── cli.py          #   argparse CLI（init / reindex / search / lint）
│       │       ├── okflib.py       #   零依赖 OKF v0.1 库（stdlib only）
│       │       ├── validate_okf.py #   okflib 的 CLI 前端（lint）
│       │       ├── indexlib.py     #   L2 sqlite-vec + fastembed 索引库（opt-in）
│       │       ├── config.py       #   ~/.config/mneme/config.toml 读写（tomllib + 手写 writer）
│       │       ├── tools_helpers.py
│       │       └── toml_writer.py  #   手写 TOML writer（替换 tomli_w）
│       └── references/             #   workflow + spec 文档（按需加载）
│           ├── workflow-ingest.md
│           ├── workflow-query.md
│           ├── workflow-lint.md
│           ├── type-vocab.md
│           ├── wiki-structure.md
│           └── index-design.md
├── dist/mneme-*.zip                #   唯一发布物（gitignored；构时生成）
├── sample-bundle/                  # 工程层：合规示范 / 测试夹具（非真 wiki）
├── tests/                          # 工程层：okflib TDD 测试 + fixtures/
├── .research/                      # 工程层：立项研究档案（upstream/ verbatim MIT 副本）
└── docs/                           # 工程层：specs + plans
    └── superpowers/
```

`scripts/mneme/` 子目录是真正的 Python 包（zip-only 交付的标准布局）。`scripts/mneme.py` 是给 skill.sh 用户用的入口 shim（`python3 ~/.claude/skills/mneme/scripts/mneme.py <subcmd>`）。**唯一发布物是 `dist/mneme-<v>.zip`**——没有 wheel、没有 `pip install mneme`、没有 setuptools。需要语义判断的工作流继续由宿主 agent 按 `SKILL.md` 执行。wiki 仍走**外部 bundle 模型**——`sample-bundle/` 只是测试夹具，真 wiki 路径由 `~/.config/mneme/config.toml` 的 `bundle_path` 指定。

安装从 [skill.sh](https://skill.sh) 一键装到 `~/.claude/skills/mneme/`，只把 skill 本体暴露给 agent，工程文件不进上下文。真 wiki bundle 在仓库外，路径由 `~/.config/mneme/config.toml` 的 `bundle_path` 指定（见 spec §5）。

## 在本仓库工作的约定

1. **先读 `.research/`**。任何修改 OKF 合规性的决定，必须能在 `.research/upstream/OKF-SPEC.md` 中找到依据；拿不准时回原文，不要凭记忆改约束。
2. **`upstream/` 目录只读**。其中的文件是上游规范的 verbatim 副本（MIT），**禁止**给它们加 frontmatter 或改动正文——那会破坏“权威参考副本”的语义。要扩展规范，写提案放 `docs/proposals/`，并标注“向后兼容、不动任何 MUST”。
3. **保持容错消费契约**。写消费者/校验器时，对缺失可选字段、未知 `type`、断链等只告警不拒绝。
4. **概念 ID = 文件路径去 `.md`**。不需要额外 ID 系统。移动文件即改 ID，需同步更新引用。
5. **链接用绝对 bundle-relative 形式**（`/tables/customers.md`），除非确需相对链接。
6. **每次 ingest 都更新 `index.md` 与 `log.md`**。`log.md` 条目用一致前缀（如 `## 2026-07-06 ingest | <标题>`），使其可被 unix 工具解析：`grep "^## " log.md | tail -5`。
7. **图片不是一等公民**。OKF/Mneme 中图里的知识必须先抽成文字才能被 agent 用上（Karpathy 原文提醒：LLM 无法在一次读取里原生读懂含内嵌图片的 Markdown）。
8. **网络受限环境**。本机在中国大陆，WebSearch 不可用，Wikipedia/DuckDuckGo 受 DNS 污染；做调研走 Bing（`www.bing.com/search`）+ GitHub raw/API，或让用户用 `! <cmd>` 在会话内执行需要代理的命令。

## 非目标

- 不定义固定的概念类型 taxonomy（`type` 值不集中注册）。
- 不规定存储 / 服务 / 查询基础设施（除参考实现）。
- 不替代领域 schema（Avro / Protobuf / OpenAPI）——OKF 引用它们，不吞并它们。
- v1 不做：远程/云索引（本地 sqlite-vec only）、多 bundle 管理、PDF/Office/URL 摄取（v2 converters 仍 deferred）、query 回填仅提议。
- v1 不实现 MCP server（CLI+skill 已覆盖；见 spec §15 未来条目）。

## 下一步

v2 已落地；后续（v2.1+）：

1. **v2 converters**（Word / PDF / PPT / Excel / 图片 / HTML → md/csv）—— 薄封装现有库 + lazy import + `mneme[converters]` extras。
2. **首次实际 ingest**：把 `/Users/scott1743/Desktop/佳都/飞书文档库/` 的 141 个 `.md` 作为 raw 素材，由加载 mneme skill 的宿主 agent 执行 `init` + `ingest`，蒸馏成 OKF 概念页并建立 L2 索引。
3. **MCP server**（按需）：仅当出现跨客户端共享或一等工具需求时再加。
4. **dogfood**：把 `.research/` 本身也视作一个 OKF bundle 来审视（参考 awesome-okf 的 dogfooding 做法）。

---

*本项目立项于 2026-07-06。研究资料采集方法见 [`.research/README.md`](.research/README.md)。*
