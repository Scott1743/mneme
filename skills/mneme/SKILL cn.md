---
name: mneme
version: 1.1.0
description: "维护与检索本地、OKF v0.1 合规的 LLM 知识库（research / learning notes）。当用户想摄入资料、搜索 / 查询 wiki、lint、reindex、初始化 wiki 时使用。触发词：'mneme'、'我的 wiki'、'搜索知识库'、'摄入笔记'、'查 wiki'、'lint wiki'、'知识库'。v1.1.0 采用 skill-first 交付（skill.sh）、OKF 核心零依赖、L2 语义搜索懒装（首次 search/reindex 自动安装）。dream（定时自动策展）按设计缺席 —— 见 CHANGELOG 的 freeze 说明。"
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
  - AskUserQuestion
---

# mneme — 轻量 LLM wiki

所有 mneme 操作通过原生工具（Read / Write / Edit / Bash / Glob / Grep）加 skill 自带的薄 CLI 驱动。**绝不**调用任何独立 agent SDK 或 `@tool` 框架 —— 你的原生工具就是 agent runtime。

## Skill 安装

本 skill 通过 [skill.sh](https://skill.sh) 分发，落点在：

```text
~/.claude/skills/mneme/
├── SKILL.md                    ← 英文版（权威）
├── SKILL cn.md                 ← 你正在读这里
├── references/                 ← workflow + spec 文档（按需加载）
└── scripts/
    ├── mneme.py                ← CLI 入口 shim
    └── mneme/                  ← Python 包（cli / okflib / indexlib / ...）
```

任何 Bash 块中调用 CLI：

```bash
python3 ~/.claude/skills/mneme/scripts/mneme.py <subcmd> [args]
```

mneme 在 bundle 外部维护一个 OKF v0.1 知识库。skill 包含 7 个 scenario，按用户意图选一个。

## Step 0：解析 bundle（每个 scenario 都要做）

按以下顺序找 wiki bundle，用第一个命中：

1. `~/.config/mneme/config.toml` 的 `bundle_path` 键。
2. `MNEME_BUNDLE` 环境变量。
3. 用户给定的显式路径。
4. 自动发现：从 cwd 向上找根 `index.md`，frontmatter 含 `okf_version`。
5. `./wiki`（若存在）。
6. 都未命中 → 问用户路径，或建议跑 `init`。

Helper：

```bash
Bash: python3 ~/.claude/skills/mneme/scripts/mneme.py --help
```

> **L2（语义搜索）是懒装的。** `search` 和 `reindex` 子命令需要 `sqlite-vec` + `fastembed`（首次调用下载 ~90MB BGE 模型）。skill 的 `ensure_index_deps()` 会在首次 L2 调用时自动触发 `pip install mneme[index]` —— 用户不需要跑任何安装步骤。如果安装失败（离线 / 权限拒绝），CLI 退出并给出清晰提示，告诉用户手动跑 `pip install 'mneme[index]'`。

## OKF v0.1 合规（硬规则 —— 写入时绝不违反）

1. 每个非保留 `.md` **必须**有 `---` 分隔的 YAML frontmatter 块。
2. 每个 frontmatter **必须**有非空 `type`。
3. 保留文件 `index.md`（无 frontmatter，根可有 `okf_version`）和 `log.md`（日期前缀时间线）遵守各自结构。

**不要**拒未知 `type` 值、多余 frontmatter key、断链 —— 仅警告。

## type 词表（推荐，非注册）

`Concept`（idea / topic） · `Reference`（distilled external source） · `Summary`（synthesis） · `Source`（`sources/` 里的原始资料）。

## Scenario: init <path>

搭一个 OKF bundle 并记录位置：

1. `Bash: python3 ~/.claude/skills/mneme/scripts/mneme.py init <path> [--config <cfg>]`（路径相对 cwd；省略 `--config` 时默认 `~/.config/mneme/config.toml`）。
2. 验证：`<path>/index.md` 有 `okf_version: "0.1"`，`<path>/log.md` 存在，`<path>/sources/.gitkeep` 存在。
3. 向用户确认；bundle 路径现在可通过 Step 0 发现。

## Scenario: reindex [--config <cfg>]

从零重建 L2 sqlite-vec 索引：

1. `Bash: python3 ~/.claude/skills/mneme/scripts/mneme.py reindex [--config <cfg>]`。
2. 首次运行触发 `ensure_index_deps()`，装 `mneme[index]`（sqlite-vec + fastembed）并下载 ~90MB BGE 模型；之后运行用缓存的依赖。
3. 确认输出：`indexed N concepts into <bundle>/.mneme/index.db`。

每次 `ingest` 增删 / 合并页面后跑 `reindex`。

## Scenario: search <query>

返回排序的 L2 检索命中，不综合答案也不修改 bundle：

1. `Bash: python3 ~/.claude/skills/mneme/scripts/mneme.py search "<query>" --json [--type <type>] [-k <limit>]`。
2. 首次运行同 `reindex` 的 `ensure_index_deps()` 流程（首次调用装 L2 依赖 + 下模型）。
3. 展示命中的标题、bundle 相对路径、类型、snippet。
4. 不要自动 reindex。索引缺失或不兼容时，提示用户 CLI 修复方法（`python3 ~/.claude/skills/mneme/scripts/mneme.py reindex`）。

查询以 shell 参数传入，绝不拼接到 Python 源码。search snippet 是导航辅助，Markdown 概念页才是权威。

## Scenario: ingest <source path>

把资料（论文 / 文章 / 笔记）蒸馏成 OKF 概念页：

0. **保留原始资料（不可变 artifact）。** 读源做蒸馏之前，把原始文件原样复制到 `<bundle>/sources/<basename>`，让原始输入作为 OKF v0.1 source-of-truth 与蒸馏出的概念页并存。如果目标已存在且内容不同，终止并问用户 —— 不覆盖。
1. `Read <source path>` 取全文。
2. 决定怎么拆成概念页（每页一个原子观点；一份源可拆 1–15 页）。
3. 每页：
   - `Write <bundle>/concepts/<slug>.md`，frontmatter 含 `type` / `title` / `description` / `tags` / `timestamp` / `resource` + 正文。
   - 相关页面用绝对 bundle 相对路径互链（`/concepts/other.md`）。
4. `Edit <bundle>/index.md` —— 找到或创建章节标题：`## <section>`（如 `## Concepts`、`## References`、`## Summaries`）已存在则在它下面追加 `* [Title](path) - description`；否则追加新 `## <section>` 标题与条目。用 frontmatter `type` 选 section。
5. `Edit <bundle>/log.md` —— **prepend**（插到顶部）`## YYYY-MM-DD ingest | <source title>` + 一行说明。OKF v0.1 log 契约要求 newest-first。
6. `Bash: python3 ~/.claude/skills/mneme/scripts/mneme.py reindex`（首次触发 `ensure_index_deps()`）。
7. **模型加载失败时：** 不要用任何替代函数重试。把失败原样告知用户。CLI 的离线 fallback 消息含 `pip install 'mneme[index]'` 手动安装指引。

详见 `references/workflow-ingest.md`。

## Scenario: query <question>

朴素 RAG：embed → KNN → top-k → 读页 → 带引用综合：

1. `Bash: python3 ~/.claude/skills/mneme/scripts/mneme.py search "<question>" --json -k 10`。
2. 对每个 top chunk，`Read <bundle>/<chunk.path>`（用 search 结果的 `concept_id` 推路径：`concepts/foo` → `concepts/foo.md`）。
3. 综合答案并加 **inline citations**（bundle 相对 markdown 链接）：`[Foo](/concepts/foo.md)`。
4. 如果答案泛用且无页面覆盖，**提议**（不自动写）回填成新的 `Summary` 页面。
5. 诚实告知缺口：wiki 覆盖不足时说清楚并建议 `ingest`。

详见 `references/workflow-query.md`。

## Scenario: lint

策展 + 报告（**不**自动改）：

1. `Bash: python3 ~/.claude/skills/mneme/scripts/mneme.py lint <bundle>` —— 读 ERROR（必改）和 WARNing。
2. 抽样读几页；找矛盾 / 过时 timestamp / 缺交叉引用。
3. 写策展报告到 `<bundle>/lint-report-<date>.md`（**不**改文件；让用户决定）。

详见 `references/workflow-lint.md`。

> **dream（定时全自动）按设计缺席。** dream workflow 的相似度数学引用了不存在的 `find_orphans()` 原语、在解析 bundle 之前跑 `git add -A`、可能自动 commit 用户未关的内容。恢复前提：(a) Phase 5 retrieval benchmark 通过；(b) `find_orphans` + 相似度安全工作流经测试；(c) dry-run preview 模式 + 独立 safety TDD 套件。见 `CHANGELOG.md` 0.2.1 条目。

## references（按需加载）

`references/workflow-ingest.md` · `references/workflow-query.md` · `references/workflow-lint.md` · `references/type-vocab.md` · `references/wiki-structure.md` · `references/index-design.md`。

OKF 规范：<https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md>。