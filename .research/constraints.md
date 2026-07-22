# Mneme 硬约束

本文件把 mneme 必须遵守的硬约束蒸馏成一张速查表。所有 OKF 相关条目均可在 [`upstream/OKF-SPEC.md`](upstream/OKF-SPEC.md) 中找到对应章节；项目约束来自本项目的定位。**冲突时以 OKF SPEC 原文为准。**

## A. OKF v0.1 合规（SPEC §9）

一个 bundle 符合 OKF v0.1 当且仅当：

1. **frontmatter 可解析**：树中每个**非保留** `.md` 文件，顶部都含 `---` 界定的 YAML frontmatter 块。
2. **`type` 非空**：每个 frontmatter 块都含非空 `type` 字段（**唯一必填字段**）。
3. **保留文件结构**：`index.md`（§6）、`log.md`（§7）出现时须分别遵循其结构。

## B. frontmatter schema（SPEC §4.1）

| 字段 | 必要性 | 说明 |
|---|---|---|
| `type` | **REQUIRED** | 短字符串，标识概念种类；值**不集中注册**；消费者容忍未知值。示例：`Table`、`API Endpoint`、`Metric`、`Playbook`、`Reference`、`Concept`。 |
| `title` | recommended | 人类可读显示名；缺省时消费者可从文件名推导。 |
| `description` | recommended | 单句摘要；供 `index.md` 生成、搜索片段、预览。 |
| `resource` | recommended | 底层资产的规范 URI；抽象概念可省。 |
| `tags` | recommended | YAML 字符串列表，跨切面分类。 |
| `timestamp` | recommended | ISO 8601 最后有意义修改时间。 |
| `okf_version` | 仅 bundle 根 `index.md` 可带 | 声明目标版本，如 `"0.1"`。 |
| *(任意扩展)* | optional | 生产者可加任意键；消费者须保留未知键、不得因未知键拒绝。 |

## C. 保留文件（SPEC §3.1, §6, §7）

- **`index.md`**：目录索引，支持**渐进式展开**。**不含 frontmatter**（唯一例外：bundle 根 `index.md` 可带 `okf_version`）。正文按小节分组，每条形如 `* [Title](relative-url) - short description`，描述宜取自被链概念的 `description`。可自动生成；缺失时消费者可现场合成。
- **`log.md`**：变更时间线，newest-first，日期标题用 ISO 8601 `YYYY-MM-DD`。条目为散文，前导粗体词（`**Update**`/`**Creation**`/`**Deprecation**`）是约定非要求。建议统一前缀以便 `grep` 解析。
- 这两个文件名在任意层级都有定义含义，**不得**用作概念文档。

## D. 链接（SPEC §5）

- **绝对 bundle-relative**（以 `/` 开头，如 `/tables/customers.md`）：**推荐**，文件在子目录内移动时仍稳定。
- **相对链接**（`./other.md`）：标准 Markdown 形式，可用。
- 链接语义由周围散文表达（references / joins-with / depends-on …），链接本身不携带关系类型。
- **消费者必须容忍断链**——目标不存在不算畸形，可能只是“尚未写就的知识”。

## E. 概念文档正文（SPEC §4.2, §8）

- 正文为标准 Markdown；**优先结构化**（标题 / 列表 / 表格 / 围栏代码块）而非自由散文，利于人与 agent 检索。
- 无必填正文节。约定含义的标题：`# Schema`（结构化字段描述）、`# Examples`（用法示例）、`# Citations`（外部来源）。
- **Citations** 置于文末 `# Citations` 下，编号形式；可为绝对 URL、bundle-relative 路径、或 `references/` 子目录下的镜像概念。

## F. 容错消费契约（SPEC §9，写消费者/校验器时必须遵守）

消费者**不得**因以下任一情况拒绝 bundle：

- 缺失可选 frontmatter 字段；
- 未知 `type` 值；
- 未知额外 frontmatter 键；
- 断链；
- 缺 `index.md`。

一个文件不合规**不得**影响其他文件可用性。校验器只对硬规则 1–3 报错，其余只告警。

## G. 项目约束（mneme 自身定位）

| # | 约束 | 理由 |
|---|---|---|
| G1 | **仅本地文件系统**：无 DB / 服务端 / SDK / 云 / 构建步骤 | Karpathy：中等规模下 `index.md` 即可免 RAG 基建；OKF：能 `cat` 就能读 |
| G2 | **载体是 agent skill**（Claude Code `SKILL.md` 格式） | OKF 官方即以 skill 教 agent 产出合规 bundle；skill = Karpathy 三层架构的 schema 层 |
| G3 | **轻量优先**：3 条规则，不是 300 条 | OKF 哲学；降低采纳与维护成本 |
| G4 | **git-native**：bundle 即仓库/目录 | 知识像代码一样 diff / branch / review |
| G5 | **零第三方依赖**：脚本只用标准库 | 与 OKF “无运行时”一致；产物须过一致性校验 |
| G6 | **最小意见、自由扩展** | 只标准化自描述所需最小结构集；余者留给生产者 |
| G7 | **raw/OKF 命名空间分离**：`sources/*.md` 只放 OKF `Source` 页；不可变原件放 `raw-sources/`，Markdown 原件追加 `.raw` 后缀 | SPEC §3.1 把所有非保留 `.md` 定义为概念文档；不能靠目录豁免绕过 MUST |

## H. 命名与约定

- **概念 ID = 文件路径去 `.md`**（如 `tables/users.md` → `tables/users`）。移动文件即改 ID，须同步更新引用。
- **链接**：默认绝对 bundle-relative（`/...`）。
- **timestamp**：ISO 8601，如 `2026-07-06T14:30:00Z`。
- **log 条目前缀**：`## YYYY-MM-DD <op> | <标题>`，op ∈ {ingest, query, lint, update, create, deprecate}。
- **UTF-8** 编码。

## I. 禁止项

- ❌ 引入数据库 / 服务端 / SDK / 云依赖 / 构建步骤。
- ❌ 在 `upstream/` 的 verbatim 副本上加 frontmatter 或改正文（破坏权威副本语义）。
- ❌ 校验器/消费者因可选字段缺失、未知 `type`、断链等**拒绝** bundle（违反容错消费契约）。
- ❌ 把图片当一等公民——图里的知识必须先抽成文字。
- ❌ 定义固定 `type` taxonomy 或替代领域 schema（Avro/Protobuf/OpenAPI）。
- ❌ 在未读 `upstream/OKF-SPEC.md` 原文的情况下凭记忆改 OKF 合规约束。
