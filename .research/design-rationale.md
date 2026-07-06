# 设计推演：Karpathy LLM Wiki → OKF → Mneme

本文解释 mneme 为什么长成这样。核心论点：**mneme 不是新发明，而是把一条已经成立的谱系——Karpathy 的 LLM Wiki 思想、Google 的 OKF 协议、agent skill 载体——收束到一个本地优先、零依赖的实现里。**

> 谱系一手材料见 [`upstream/karpathy-llm-wiki.md`](upstream/karpathy-llm-wiki.md)（MIT，对 Karpathy gist 的中文梳理）与 [`upstream/OKF-SPEC.md`](upstream/OKF-SPEC.md) §10。中文社区解读见 [`references.md`](references.md)。

## 1. 思想源头：Karpathy 的 LLM Wiki

2026-04-04，Andrej Karpathy 发布 *LLM Wiki* gist。核心隐喻：

> “Obsidian 是 IDE；LLM 是程序员；wiki 是代码库。”

主张：**不要每次提问都对原始文档做 RAG 检索（等于每次从零重新发现知识），而是让 LLM 增量地构建并维护一座持久的 wiki**——一堆互链的 Markdown 页面，夹在你和原始资料之间。知识只编译一次，然后持续保鲜、复利累积。

### RAG vs LLM Wiki

| | RAG | LLM Wiki |
|---|---|---|
| 知识 | 每次查询临时检索片段 | 一次编译成持久产物，持续累积 |
| 交叉引用 | 每次重新拼 | 已经在那儿了 |
| 矛盾 / 过时 | 不处理 | 已被标注 |
| 随时间 | 不增值 | 越用越富 |

关键词：**持久、复利（compounding）**。人负责找源、探索、问对问题；LLM 负责总结、交叉引用、归档、记账这些“没人愿意干但让知识库真正有用”的脏活。

### 三层架构

1. **Raw sources**——精选的源文档，**不可变**，LLM 只读不改，事实来源。
2. **The wiki**——LLM 生成的 Markdown 目录：摘要、实体页、概念页、对比、总览。这层 LLM 完全拥有，人只读。
3. **The schema**——一份告诉 LLM “wiki 怎么组织、有哪些约定、工作流怎么走”的文档（如 `CLAUDE.md` / `AGENTS.md`）。它让 LLM 成为**有纪律的 wiki 维护者**，而非泛泛的聊天机器人。

### 三种操作

- **Ingest**：丢新源 → 读、讨论要点、写摘要页、更新索引、更新相关页、往 log 追加一条（一个源可能动 10–15 个页面）。
- **Query**：对 wiki 提问 → 找相关页、读、带引用综合作答；好答案可回填成新页面。
- **Lint**：定期体检——找矛盾、过时论断、孤儿页、缺页、缺失交叉引用。

### 两个特殊文件

- **`index.md`**：面向内容的目录，每页一条链接 + 一句话摘要，按类别组织，每次 ingest 更新。**先读索引再钻页面**——在中等规模（~100 源、数百页）出奇地好用，免掉 embedding RAG 基建。
- **`log.md`**：面向时间的只读追加记录，条目以一致前缀开头，可被 unix 工具解析（`grep "^## \[" log.md | tail -5`）。

> Karpathy 原文还提醒一个被 mneme 继承的痛点：**LLM 无法在一次读取里原生读懂含内嵌图片的 Markdown**——图里的知识必须先抽成文字。

## 2. 碎片化问题

Karpathy 这套“个人约定”过去一年被无数团队各自实现了一遍：`AGENTS.md`、`CLAUDE.md`、Obsidian vault、`index.md` + `log.md` 的文件夹……**每种实现都不兼容**。同一个“LLM wiki”模式，有 100 种互不互通的变体——生产者 A 写的 bundle，消费者 B 读不了。

这是标准化的经典时机：模式已验证、实现已碎片化、互通价值已显现。

## 3. 标准化：Google OKF v0.1

2026-06-12，Google Cloud（Sam McVeety、Amir Hormati 等，Data Cloud 团队）发布 **Open Knowledge Format (OKF) v0.1**，MIT 许可。它做的事，用一句话概括：

> **把 Karpathy 这套自用模式补上“不同生产者/消费者之间互通”的那一小层契约。**

OKF 几乎原样吸收了 Karpathy 的两个特殊文件——`index.md`（渐进式展开，§6）、`log.md`（日期前缀时间线，§7）——并钉死三件最小的事（SPEC §9）：frontmatter 可解析、`type` 非空、保留文件结构。其余全部留白。

OKF SPEC §10 明确把自身定位为“LLM 'wiki' 仓库”这一既有模式的**指定化（specified）**版本：pin 下互通所需的最小规则，不规定工具。

### OKF 的关键设计决策

- **概念 ID = 文件路径去 `.md`**：不需要额外 ID 系统。
- **Markdown 链接 = 关系图**：概念间用标准链接互引，目录自动变成知识图谱，比纯文件系统父子层级丰富。
- **容错消费**：消费者必须容忍未知 `type`、缺失可选字段、断链——一个文件不合规不影响其他文件。
- **最小意见、自由扩展**：只标准化自描述所需的最小结构集。

## 4. 为什么载体是 agent skill

OKF 官方不止发布规范，还发布了一个**参考 agent**（自动遍历 BigQuery 数据集生成 OKF 概念文档）和一份**可视化器**。更关键的是，OKF 生态里**已把 “教 agent 产出合规 bundle 的 skill” 当作一等交付物**——`okf.md` 站点明言：“Install a skill that teaches Claude, Codex, or Cursor to produce conformant bundles.”

这恰好对上 Karpathy 三层架构中的 **schema 层**：一份告诉 LLM “wiki 怎么组织、工作流怎么走”的文档。把 schema 层实现成一个**可安装、可复用、跨项目携带的 agent skill**（而非每个仓库各写一份 `CLAUDE.md`），正是消除第 2 节那“100 种不兼容重复造轮”的正确姿势——skill 是可分发的 schema。

因此 mneme 的载体定为 Claude Code agent skill（`SKILL.md` + `references/` + `scripts/`）。`SKILL.md` 定义 ingest / query / lint 三工作流，约束 agent 产出 OKF 合规 bundle；`CLAUDE.md` 是项目级宪法（也是 schema 层的一部分）。

## 5. 为什么仅本地文件系统

两条理由：

1. **Karpathy 的规模洞察**：中等规模（~100 源、数百页）下，`index.md` 的渐进式展开即可免掉 embedding / 向量 RAG 基建。先读索引再钻页面，足够好用。只有规模化到“索引也装不下”时才需要外挂检索（如 `qmd` 这类本地 BM25+向量+LLM 重排工具）。
2. **OKF 的“无运行时”哲学**：bundle 是一个目录的 Markdown，能 `cat` 就能读，能 `git clone` 就能 ship，不绑定云 / 数据库 / 模型厂商 / agent 框架。

“本地文件系统 only” 不是限制，而是这两条思想的水到渠成——也是 mneme “轻量”承诺的物理基础。

## 6. Mneme 的位置

在 Karpathy 三层架构里，mneme 同时是：

- **schema 层**：`CLAUDE.md`（项目宪法）+ `SKILL.md`（agent 维护规约）——告诉 agent 怎么维护 wiki。
- **wiki 维护工具**：以 skill 形式封装 ingest / query / lint，让 agent 成为一个有纪律的维护者。

在 OKF 生态里，mneme 是**本地优先、零依赖、面向个人/小团队**的 skill 实现——区别于官方参考 agent（绑 BigQuery + Gemini）和企业级 producer 插件。它的价值不在功能多，而在**把 Karpathy 思想 + OKF 契约收束到一个开箱即用、可 git 化、无任何外部依赖的最小实现**。

## 一句话总结

> Karpathy 给了思想（编译一次、复利维护的 LLM wiki），Google 给了契约（OKF 的 3 条合规规则），mneme 把两者收束到一个本地优先的 agent skill——让任何 agent 都能像维护代码一样维护一座合规的知识 wiki。
