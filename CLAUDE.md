# Mneme — 轻量化 LLM Wiki

> Mneme（摩涅墨叙涅），希腊神话中的记忆女神。本项目是一座**生于本地文件系统、由 Agent 增量维护**的轻量 LLM 知识 wiki。

## 这是什么

Mneme 是一个以 **agent skill 为载体**的轻量化 LLM wiki。它：

- **继承** Andrej Karpathy 的 *LLM Wiki* 思想（2026-04-04 gist）——把知识当代码编译一次、持续复利，而非每次提问重新检索；
- **服从** Google 发布的 **OKF (Open Knowledge Format) v0.1** 协议（2026-06-12，MIT）——一个目录的 Markdown + YAML frontmatter，3 条规则，无运行时；
- **载体**是一个通过 [skill.sh](https://skill.sh) 分发的 Claude Code agent skill —— `SKILL.md` 教会 agent 像维护源码一样增量维护一座 OKF 合规的 wiki。

一句话：**让 agent 在一个本地 Markdown 目录上，增量地编译、查询、体检一座 OKF 合规的知识 wiki。**

v2.0 起交付仍是**单一 skill zip** —— 没有 wheel，没有 wheel / 全包 `pip install`，没有 setuptools。从 skill.sh 一键安装到 `~/.claude/skills/mneme/`，agent 直接用。OKF 核心与默认 L1（SQLite FTS5）零依赖；3.x 可由用户显式选择语义召回。

## 思想谱系

```
Karpathy LLM Wiki (2026-04-04 gist)
        │  “Obsidian 是 IDE；LLM 是程序员；wiki 是代码库。”
        │  三层架构 + dream/search + index.md/log.md
        ▼
各团队各自实现（AGENTS.md / CLAUDE.md / Obsidian vault / index.md+log.md）
        │  一百种互不兼容的重复造轮
        ▼
Google 标准化为 OKF v0.1 (2026-06-12)  ← 把 Karpathy 的“个人约定”
        │                                补上“跨生产者/消费者互通”的契约
        ▼
Mneme：把 OKF 落成本地优先、零依赖、agent 驱动的 skill
        │
        ▼
v2.0：把 user surface 收成 dream + search；
v2.2：完成 workflow 契约迁移；v3.3：持久化显式可选 L2 + 独立索引缓存；
v4.0：新增可删除的 SQLite Graph 与 Graph + FTS5 hybrid 检索
```

详见 [`.research/design-rationale.md`](.research/design-rationale.md)。

## 四层架构（v2.0 — 包含 disposable accelerator）

| 层 | 角色 | 谁拥有 | 在 mneme 中的位置 |
|---|---|---|---|
| **Raw sources** | 不可变原始资料 | 用户只读 | `wiki/raw-sources/`（Markdown 原件用 `*.md.raw`，或外部路径引用） |
| **OKF Wiki** | 唯一真相源；type + tags + links | LLM agent 完全维护 | `wiki/` —— OKF bundle 本体 |
| **Agent Skill** | 行为规约 | 人 + agent 共写 | `~/.claude/skills/mneme/SKILL.md` + `references/` |
| **Disposable accelerator** | 可删除的导航缓存 | 不拥有事实 | `wiki/.mneme/graph.db` + `wiki/.mneme/fts.db` + `wiki/.mneme/l2.db`（显式启用后） |

> 本文件即 Karpathy 思想中真正的 **schema 层**：它让 agent 成为有纪律的 wiki 维护者，而非泛泛的聊天机器人。

## 用户表面：`dream` 与 `search`

v2.0 把用户叙事收成两个动词：

- **`dream`（写侧总入口）** —— 你丢资料进来，agent 读它、写 OKF 概念页、加 `tags`、做互链、更新 `index.md` 与 `log.md`。`mneme dream` 子命令本身是**只读审计**（出报告，不改 wiki）；真正的写盘在 SKILL.md 工作流里、由 agent 用 `Write` / `Edit` 完成。交互式 dream 每次写盘前必须先得到你点头；每天 02:00 的宿主 agent 夜巡只有在用户创建任务时明确选择“受限自动修复”后，才获得健康修复白名单内的持续授权。
- **`search`（读侧总入口）** —— 你问问题，agent 先读 `index.md`，按 tags / 标题 / 链接 / `grep` 渐进展开；wiki 大的时候按 Graph + FTS5 hybrid 召回，显式启用 L2 后把语义候选加入同一个页面级融合排序。Graph 不可用时其余已激活通道继续工作；`mneme search` 只返回候选与导航上下文，最终答案由 agent 读完整页综合，引用是 bundle 内路径。

`init / lint / reindex / dream / search / convert` 是 agent 在后台调用的确定性 CLI 子命令，不增加用户动词。

## OKF v0.1 + tags 写作纪律

一个 bundle **符合 OKF v0.1** 当且仅当（SPEC §9）：

1. 树中每个**非保留**的 `.md` 文件都含可解析的 YAML frontmatter 块。
2. 每个 frontmatter 块都含**非空 `type` 字段**（唯一必填字段）。
3. 保留文件名 `index.md` / `log.md` 出现时，分别遵循 §6 / §7 的结构。

**frontmatter schema**（SPEC §4.1）：

```yaml
---
type: <Type name>            # REQUIRED（OKF 协议级 MUST）。短字符串，消费者据之路由/过滤。
title: <display name>        # recommended
description: <one-line>      # recommended
resource: <canonical URI>    # recommended；抽象概念可省
tags: [<tag>, ...]           # recommended——mneme 写作纪律：自己写的页至少 1 个 tag
timestamp: <ISO 8601>        # recommended，最后修改时间
okf_version: "0.1"           # 仅 bundle 根 index.md 可带，声明目标版本
---
```

**保留文件**：`index.md`（目录索引，支持渐进式展开，无 frontmatter；仅 bundle 根可带 `okf_version`）；`log.md`（日期前缀的时间线，newest-first）。

**链接**：概念间用标准 Markdown 链接。**绝对 bundle-relative 形式**（以 `/` 开头，如 `/tables/customers.md`）为推荐形式——文件在子目录内移动时仍稳定。

**容错消费契约（SPEC §9，必须遵守）**：消费者**不得**因以下任一情况拒绝一个 bundle：缺失可选 frontmatter 字段、未知 `type` 值、未知额外 frontmatter 键、断链、缺 `index.md`。一个文件不合规不得影响其他文件可用性。

> 完整规范原文（MIT，verbatim）见 [`.research/upstream/OKF-SPEC.md`](.research/upstream/OKF-SPEC.md)。蒸馏后的硬规则见 [`.research/constraints.md`](.research/constraints.md)。

### `type` / `tags` / 链接 —— 三者语义不重叠

| 字段 | 角色 | 例子 |
|---|---|---|
| `type` | 文档角色（OKF 协议级 MUST） | `Concept` · `Reference` · `Summary` · `Source` |
| `tags` | 主题归类（mneme 写作纪律：≥1） | `[okf]`，`[llm-wiki]`，`[source]` |
| Markdown 链接 | 具体关系 | `/concepts/okf.md` |

- **type** 不集中注册；OKF 容错消费契约要求消费者**不**因未知 `type` 拒收。
- **tags** 没全局 taxonomy，词汇由每座 wiki 在 `index.md` 中渐进成长；消费外部 OKF 时缺 tags 只 WARN。
- **Topic 页面**（如 `topics/llm-wiki.md`）可以写——它就是一份普通 OKF `Topic` 页面，承担"按主题聚合概念"的角色。不要为每个 tag 镜像一份 `tags/<tag>.md`，维护成本高且容易腐化。
- **链接** 用绝对 bundle-relative 形式（`/tables/customers.md`），除非确需相对链接。

## 项目硬约束

- **仅本地文件系统**：无远程数据库、服务端、SDK、云；允许本地 disposable SQLite Graph/FTS5/L2 缓存，不提供常驻服务。能 `cat` 就能读，能 `git clone` 就能 ship。
- **载体是 agent skill**：遵循 Claude Code skill 格式（`SKILL.md` + YAML frontmatter：`name` / `description` / `allowed-tools` 等，可附 `references/` 支撑文档与 `scripts/` 脚本）。
- **git-native**：bundle 即仓库/目录，知识像代码一样 diff / branch / review / blame。
- **严格 OKF 边界**：`sources/*.md` 是带 frontmatter 的 `type: Source` 溯源页；不可变原件放 `raw-sources/`。原件若以 `.md` 结尾，落盘时追加 `.raw`，避免被 OKF §3.1 解释为概念页。校验、Dream、索引与 Web UI 不得对任何业务目录设置 `.md` 豁免。
- **分层依赖**：OKF 核心、FTS5 与 v4 Graph（`okflib` + `sqlite3` + FTS5）保持 stdlib 零依赖。Graph 由 `reindex --graph` 显式重建，存在时普通 search 使用 hybrid；删除后由其余已激活通道继续召回。L2 仅在用户显式执行一次 `reindex --l2` 时启用，依赖由用户自行安装；成功后模式持久化并加入 Graph + FTS5 融合。skill 不自动执行 `pip install`，激活的 L2 失败时不静默回退。
- **disposable accelerator**：`graph.db` / `fts.db` / `l2.db` 可删可重建；不是事实来源；删除后 wiki 仍然完整。v4 Phase 1 只从页面、tags 与 Markdown links 派生 Graph，不把结构化事实从 OKF 正文迁出。
- **按需、无自建常驻服务**：dream / search 走 host-agent 本地工具（Read / Write / Edit / Bash / Grep / Glob），skill 自身只提供 OKF 合规骨架与确定性 CLI（`mneme init / lint / reindex / search / dream / convert`）；每天 02:00 的可选夜巡由宿主 agent 的 recurring-task 能力唤醒，不引入 Mneme daemon，MCP 暂不实现。
- **dream 默认 preview-only，夜巡修复显式 opt-in**：交互式 dream 写盘前必须先展示报告并等待用户明确点头。首次建库或首次成功 dream 后，skill 可引导用户创建每天 02:00 的宿主 agent 任务，并选择“只报告”或“受限自动修复”；后者的选择只构成对无歧义健康修复白名单的持续授权。夜巡不得改事实正文或 raw source，不得新建知识页、合并、归档、移动、删除，不自动 commit / push / `git add -A`；有歧义、与用户改动重叠或涉及超过 5 个概念页时降级为报告。
- **最小意见、自由扩展**：只标准化自描述所需的最小结构集；其余留给生产者。frontmatter 可带任意额外键，消费者须保留未知键。

## 目录结构

工程过程与最终 skill 交付物分离（skill 开源最佳实践）。**唯一交付物是 `dist/mneme-<version>.zip`**——一个普通 zip 文件，对应 `~/.claude/skills/mneme/`：

```text
mneme/                              # 仓库根（开发/测试；非交付物）
├── CLAUDE.md                       # schema 层（项目宪法 + agent 维护规约）
├── AGENTS.md                       # 与 CLAUDE.md 同步（agent 面）
├── pyproject.toml                  # 仅 [tool.pytest] 配置；无 [project]，无 wheel
├── .gitignore
├── skills/
│   └── mneme/                      # ← 唯一交付物（打成 dist/mneme-*.zip）
│       ├── SKILL.md                #   dream + search；OKF + tags
│       ├── scripts/
│       │   ├── mneme.py            #   CLI 入口 shim
│       │   └── mneme/              #   Python 包（cli / okflib / indexlib / graphlib / config）
│       └── references/             #   workflow + spec 文档（按需加载）
├── dist/mneme-*.zip                #   唯一发布物（gitignored；构时生成）
├── sample-bundle/                  # 工程层：合规示范 / 测试夹具
├── tests/                          # 工程层：okflib TDD + 安全/release/docs 套件
├── introduction/                   # 工程层：GitHub Pages 介绍页（自包含 HTML）
├── .research/                      # 工程层：立项研究档案（upstream/ verbatim MIT）
└── docs/                           # 工程层：specs + plans + reports
    └── superpowers/
```

`scripts/mneme/` 子目录是真正的 Python 包。`scripts/mneme.py` 是给 skill.sh 用户用的入口 shim（`python3 ~/.claude/skills/mneme/scripts/mneme.py <subcmd>` 或 `cd scripts && python3 -m mneme ...`）。wiki 仍走**外部 bundle 模型**——`sample-bundle/` 只是测试夹具，真 wiki 路径由 `~/.config/mneme/config.toml` 的 `bundle_path` 指定。

安装时符号链接 `~/.claude/skills/mneme -> <repo>/skills/mneme`，只把 skill 本体暴露给 agent，工程文件不进上下文。真 wiki bundle 在仓库外，路径由 `~/.config/mneme/config.toml` 的 `bundle_path` 指定（见 spec §5）。

## 在本仓库工作的约定

1. **先读 `.research/`**。任何修改 OKF 合规性的决定，必须能在 `.research/upstream/OKF-SPEC.md` 中找到依据；拿不准时回原文，不要凭记忆改约束。
2. **`upstream/` 目录只读**。其中的文件是上游规范的 verbatim 副本（MIT），**禁止**给它们加 frontmatter 或改动正文——那会破坏“权威参考副本”的语义。要扩展规范，写提案放 `docs/proposals/`，并标注“向后兼容、不动任何 MUST”。
3. **保持容错消费契约**。写消费者/校验器时，对缺失可选字段、未知 `type`、断链等只告警不拒绝。
4. **概念 ID = 文件路径去 `.md`**。不需要额外 ID 系统。移动文件即改 ID，需同步更新引用。
5. **链接用绝对 bundle-relative 形式**（`/tables/customers.md`），除非确需相对链接。
6. **每次发生 wiki 写入的 dream 都更新 `index.md` 与 `log.md`**。只读报告不制造空日志。`log.md` 条目用一致前缀（如 `## 2026-07-13 dream | <标题>`），使其可被 unix 工具解析：`grep "^## " log.md | tail -5`。
7. **图片不是一等公民**。OKF/Mneme 中图里的知识必须先抽成文字才能被 agent 用上（Karpathy 原文提醒：LLM 无法在一次读取里原生读懂含内嵌图片的 Markdown）。
8. **网络受限环境**。本机在中国大陆，WebSearch 不可用，Wikipedia/DuckDuckGo 受 DNS 污染；做调研走 Bing（`www.bing.com/search`）+ GitHub raw/API，或让用户用 `! <cmd>` 在会话内执行需要代理的命令。

## 非目标

- 不实现远程 / 云索引或常驻图数据库服务；只使用本地 SQLite Graph + FTS5，另保留显式可选 L2。
- 不定义固定的概念类型 taxonomy（`type` 值不集中注册）。
- 不规定存储 / 服务 / 查询基础设施（除参考实现）。
- 不替代领域 schema（Avro / Protobuf / OpenAPI）——OKF 引用它们，不吞并它们。
- 不内建文档解析器、不自动安装 converter；`convert` 仅调用用户已有的 PDF/DOCX/PPTX 工具。
- v2 不实现 MCP server（CLI + skill 已覆盖）。

## 下一步（v4.1+）

1. **Graph Phase 2** —— 评估 agent 辅助的实体/关系深度提取与可选 embedding；任何新增结构仍必须可由 Markdown 溯源，并保持显式 opt-in。
2. **L2 质量评估** —— 只改进显式可选的候选召回，不改变 Markdown 权威性或 dream 审批契约。
3. **converter 扩展** —— 在不内建解析器、不自动安装的前提下评估更多格式与 OCR 适配。
4. **dream 审计增强** —— `dream_audit` 保持只读；夜巡由宿主 agent 在每天 02:00 执行“只报告”或显式 opt-in 的受限自动修复，合并 / 归档 / 回填仍由 agent 预览并等待用户批准。
5. **首次实际 dream** —— 把外部资料作为 raw 素材，由加载 mneme skill 的宿主 agent 执行 `mneme init` + `dream` 工作流，蒸馏成 OKF 概念页并重建 Graph + FTS5。
6. **MCP server**（按需）—— 仅当出现跨客户端共享或一等工具需求时再加。
7. **dogfood** —— 把 `.research/` 本身也视作一个 OKF bundle 来审视（参考 awesome-okf 的 dogfooding 做法）。

---

*本项目立项于 2026-07-06。研究资料采集方法见 [`.research/README.md`](.research/README.md)。*
