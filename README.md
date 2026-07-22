<div align="center">

# 📚 Mneme

**一座由 Agent 增量维护的本地 Markdown 知识 wiki**

*把知识编译一次，让每一次提问都从已经整理好的地方继续向前。*

[![MIT License](https://img.shields.io/badge/license-MIT-purple.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-4.3.0-blue.svg)](CHANGELOG.md)
[![Skills.sh](https://img.shields.io/badge/skills.sh-available-2ea44f.svg)](https://www.skills.sh/?q=mneme)

</div>

---

## ✨ 为什么选择 Mneme？

在这个 Agent 反复从零检索的世界里，每一次提问都要重新翻一遍原始资料。Mneme 把有价值的资料编译成一座本地 wiki，让后续的问题可以从已经整理好的概念、标签和链接继续向前。

**Mneme 不是一个新的云服务，也不是隐藏在数据库里的聊天记忆：**

- 原始资料留在本地文件系统，不被改写
- 知识以普通 Markdown 保存，可以直接阅读、diff 和 review
- `dream` 负责整理，写盘前必须先给你看预览
- `search` 负责召回，最终答案来自完整知识页面而不是索引片段

---

## 🌙 体验一下

<div align="center">

### 在线介绍（无需安装）

**[打开 Mneme 图文介绍 →](https://scott1743.github.io/mneme/)**

*包含产品初衷、工作方式、安装示例与本地优先设计说明*

</div>

仓库内也保留了可离线阅读的 [`introduction/index.html`](introduction/index.html)。

---

## 🧠 核心能力

### dream：把资料编译成知识

把文章、笔记或本地资料交给 Agent。它会先审计现有 wiki，再预览要新增或修改的概念页、tags、互链、`index.md` 与 `log.md`。只有得到明确批准后才会写盘。

### search：沿知识图谱寻找答案

Agent 从 `index.md` 开始，按标题、tags、链接和本地文本匹配逐层展开。wiki 变大后，可用 SQLite FTS5 或显式启用的 L2 语义索引召回候选；最终综合始终读取完整 Markdown 页面。

### 本地优先

OKF wiki 是唯一真相源。没有服务端、云数据库或强制 SDK，能 `cat` 就能读，能 `git clone` 就能迁移。

### 可删除的索引

`wiki/.mneme/fts.db` 和可选的 `wiki/.mneme/l2.db` 只是导航缓存。删掉索引不会丢失任何知识，Markdown bundle 始终完整。

---

## 🚀 快速开始

### 方式一：通过 skills.sh 安装（推荐）

```bash
npx skills add Scott1743/mneme
```

安装后会落到 `~/.claude/skills/mneme/`。重启 Agent 会话即可使用。

### 方式二：下载 Skill zip

- 零依赖基础版：[mneme-2.2.0.zip](https://github.com/Scott1743/mneme/releases/download/v2.2.0/mneme-2.2.0.zip)
- 最新版：[mneme-4.3.0.zip](https://github.com/Scott1743/mneme/releases/download/v4.3.0/mneme-4.3.0.zip)

解压到 Agent 的 skills 目录即可。Mneme 不提供 wheel 或全包 `pip install`，唯一交付物就是一个普通 Skill zip。

---

## 💬 使用示例

```text
把这份会议纪要 dream 进我的 wiki。先展示页面、标签、互链和 Graph 实体/关系预览，等我批准后再写入。
```

```text
search 我的 wiki：哪些项目使用了飞书多维表格，它们之间有什么关系？请读完整页面并引用来源。
```

```text
打开 Mneme 本地可视化面板，我想浏览页面、搜索知识图谱并检查健康状态。
```

```text
为这座 wiki 设置每天 02:00 夜巡，只报告问题，不自动修改。
```

---

## 🌿 设计理念

### 编译一次，而非反复从零检索

有价值的资料被蒸馏成稳定概念页，后续查询沿已有结构继续工作。知识像代码一样积累，而不是每轮对话重新消费。

### Markdown，而非隐藏状态

概念页、引用、索引和变更时间线都在本地目录中。用户拥有文件，也拥有完整的版本历史和迁移自由。

### 审批写入，而非自动改写

`mneme dream` 本身是只读审计。Agent 必须展示具体变更集并等待批准，不会根据相似度自动合并、归档或删除事实页。

### 最小标准，而非固定 taxonomy

Mneme 遵循 [OKF v0.1](.research/upstream/OKF-SPEC.md)：非保留 Markdown 页面必须有可解析的 YAML frontmatter 和非空 `type`。缺少可选字段、未知 `type`、额外键、断链或缺少 `index.md` 都不会让消费者拒绝整个 bundle。

Mneme 自己写出的概念页至少带一个 `tags`；具体关系由 Markdown 链接表达。`type`、`tags` 和链接各司其职。

---

## 📐 技术架构

```text
Raw sources
不可变原始资料
      │
      ▼
OKF Wiki
Markdown 唯一真相源：type + tags + links
      │
      ▼
Agent Skill
SKILL.md + 按需加载的 references
      │
      ▼
Disposable accelerator
v4 Graph + SQLite FTS5；显式可选 L2；随时可删可重建
```

四层职责彼此分离：原始资料不被改写，wiki 拥有事实，Skill 约束 Agent 行为，索引只负责导航。

---

## 🔍 检索与转换

### L1：SQLite FTS5（默认）

Python 内建 `sqlite3` + FTS5，零第三方依赖。索引位于 `<bundle>/.mneme/fts.db`。

```bash
mneme reindex
mneme search "X"
```

### v4：Graph + FTS5 混合检索

`reindex --graph` 从现有 OKF 页面、tags 和 Markdown links 原子重建 `<bundle>/.mneme/graph.db`，并刷新 FTS5。Graph 只是派生导航缓存，不修改 Markdown，也不接管事实。Graph 存在且 L2 未激活时，普通 `search` 自动使用 hybrid；没有实体命中时回退到全局 FTS5。

```bash
mneme reindex --graph
mneme search "OKF 和 FTS5 的关系" --mode hybrid
mneme search "OKF" --mode graph
```

`dream --json` 会在 `graph.db` 存在时附带实体、关系、孤立实体、未解析页面与连通分量统计；审计仍然完全只读。

### L2：语义召回（可选）

v3.3.0 起可在用户自行安装 `sqlite-vec` 与 `FastEmbed` 后，通过一次 `reindex --l2` 显式启用。模式会持久化到配置中，之后普通 `search` / `reindex` 自动沿用；切回 FTS5 使用 `reindex --fts5`。Mneme 不会自动安装依赖，也不会静默回退模式。

### 外部资料转换（可选）

Agent 无法直接读取本地 PDF、DOCX 或 PPTX 时，可以在 dream 预览阶段调用 `mneme convert`。它只使用用户已经安装的兼容转换器，不会用派生文本替换原始资料。

```bash
mneme convert report.pdf --output /tmp/report.md
```

### 夜巡 dream（可选）

首次建库或首次完成交互式 dream 后，Skill 会引导用户选择是否创建每天 `02:00` 的宿主 Agent 定时任务：

- **只报告**：Agent 执行审计、lint 和相关页面复核，不修改 wiki。
- **受限自动修复**：用户的选择构成对健康修复范围的持续授权；Agent 可修复无歧义的 frontmatter、tags、内部链接和索引项，随后校验并报告 diff。事实正文、原始资料、合并、归档、移动、删除和 git 写操作始终不在授权范围内；有歧义或超过 5 个概念页时自动降级为报告。

定时任务必须由宿主 Agent 的 recurring-task 能力创建，创建或变更前都要得到用户明确选择。`mneme dream --schedule` 仍只打印适用于 launchd、crontab 或 `schtasks` 的无 Agent、仅报告 fallback 片段，不会自行安装；其默认时间也为 `02:00`，可用 `--time HH:MM` 修改，用 `--unschedule` 生成撤销片段。

---

## 📁 项目结构

```text
mneme/
├── skills/mneme/           # 唯一可分发的 Skill 源
│   ├── SKILL.md            # dream + search 工作流
│   ├── scripts/mneme.py    # CLI 入口 shim
│   ├── scripts/mneme/      # stdlib-only Python 包
│   └── references/         # 按需加载的工作流文档
├── sample-bundle/          # OKF 合规示范与测试夹具
├── tests/                  # 分层测试
├── introduction/           # GitHub Pages 图文介绍
├── .research/              # 上游规范与立项研究
└── docs/superpowers/       # 设计、计划与报告
```

---

## 📜 设计文档

- [Mneme 2.0 产品与交互设计](docs/superpowers/specs/2026-07-13-mneme-2.0-design.md)
- [图文介绍页设计](docs/superpowers/specs/2026-07-13-mneme-introduction-redesign.md)
- [dream / search 契约对齐](docs/superpowers/plans/2026-07-14-mneme-dream-search-contract-alignment.md)
- [OKF v0.1 上游规范](.research/upstream/OKF-SPEC.md)

---

## 🛠️ 开发者指南

```bash
pip install pytest
pytest
python scripts/build_zip.py
```

默认路径保持 stdlib-only；L2 是显式可选能力。CI 覆盖 Python 3.11、3.12 和 3.13。

---

## 🤝 朋友项目

[森林密语 / 塔罗树洞](https://github.com/Scott1743/tarot-confessional)：同源、本地优先、Agent 驱动的个人反思记录。Mneme 提供「密语回响」可选联动——在塔罗解读后，把当次回响整理成可被未来查询唤醒的本地记忆。

---

## 📄 许可证

本项目采用 [MIT License](LICENSE) 开源协议。

---

<div align="center">

**让知识留在你手里。**

*Mneme，给 Agent 一座可以持续生长的本地记忆。*

</div>
