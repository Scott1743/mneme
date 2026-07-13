<div align="center">

# Mneme · 轻量化 LLM Wiki

**一个生于本地文件系统、由 Agent 增量维护的 OKF 知识 Wiki**

*把读过的东西编译一次，让知识在每次使用中继续复利。*

[![MIT License](https://img.shields.io/badge/license-MIT-6f42c1.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-1.1.0-0f766e.svg)](CHANGELOG.md)
[![OKF](https://img.shields.io/badge/OKF-v0.1-2563eb.svg)](.research/upstream/OKF-SPEC.md)
[![Skills.sh](https://img.shields.io/badge/skills.sh-mneme-111827.svg)](https://skills.sh/?q=mneme)
[![Python](https://img.shields.io/badge/python-%E2%89%A53.10-3776ab.svg)](pyproject.toml)
[![Zero--dep core](https://img.shields.io/badge/OKF_core-zero_deps-22c55e.svg)](#-零依赖-okf-核心)

[`npx skills add Scott1743/mneme`](https://skills.sh) · [`pip install mneme`](https://pypi.org/project/mneme/) · [`OKF v0.1 spec`](.research/upstream/OKF-SPEC.md)

</div>

<div align="center">

📖 完整图文介绍页：**[https://scott1743.github.io/mneme/introduction/](https://scott1743.github.io/mneme/introduction/)**（产品初衷 + 安装 + 原理）

</div>

---

## ✨ 为什么选择 Mneme？

多数知识工具让模型每次都从头检索、重新理解。Mneme 换了一种思路：让 Agent 像维护源码一样，把原始资料逐步编译成互相链接的 Markdown 概念页。

- **本地优先**：知识留在普通文件和 Git 仓库里
- **增量维护**：一次摄入，多次查询，持续修订
- **开放格式**：遵循 Google OKF v0.1，Markdown + YAML 即可互通
- **零常驻服务**：没有数据库服务、云端后台或专用运行时
- **Git 原生**：知识可以 diff、branch、review 和 blame
- **零依赖核心**：L1 lint / init / ingest / query 跑在 stdlib 上

## 🚀 快速开始

### 方式一：通过 skills.sh 安装（推荐）

```bash
npx skills add Scott1743/mneme
```

落地到 `~/.claude/skills/mneme/`，agent 直接调用：

```bash
python3 ~/.claude/skills/mneme/scripts/mneme.py init <path>
python3 ~/.claude/skills/mneme/scripts/mneme.py lint <bundle>
```

### 方式二：pip install（wheel）

```bash
pip install mneme
mneme init <path>
```

落地到 `~/.config/mneme/config.toml` 指向的 bundle。第一次跑 `mneme search` / `mneme reindex` 时自动 `pip install 'mneme[index]'`，下载约 90 MB 的 BGE 嵌入模型——只有一次，之后缓存复用。

### 方式三：从 GitHub 源码

```bash
git clone https://github.com/Scott1743/mneme.git
cd mneme
pip install -e '.[dev]'
```

把 `skills/mneme` 安装或链接到你的 Agent skills 目录后，就可以直接说：

```text
用 mneme 初始化一个 wiki，然后把这份研究笔记摄入进去。
```

## 🧠 核心能力

### Ingest · 摄入

保留不可变的原始资料（自动复制到 `<bundle>/sources/`），再把其中的知识蒸馏为可互链、可追溯的概念页，同时更新 `index.md`（按 type 分 section）、`log.md`（newest-first 顶部插入）与本地语义索引。

### Query · 查询

先定位相关概念，再读取权威 Markdown 页面进行综合回答，并用 bundle 内链接标明依据。

### Lint · 体检

检查 OKF v0.1 硬约束（frontmatter 必填 `type`、保留文件结构、YAML 严格校验）、孤儿页、断链和策展问题；未知类型与可选字段缺失只告警，不破坏容错消费契约（OKF §9）。

### Search · 检索

在资料规模增长后，按需启用 sqlite-vec + FastEmbed 的 L2 本地索引；首次调用触发 **lazy install**（`pip install 'mneme[index]'` + 模型下载），之后缓存复用。Wiki 本体始终是可直接读取的 Markdown。

## 🏛️ 三层架构

```text
原始资料 sources/          不可变的事实来源
        │
        ▼
OKF Wiki                  Agent 维护的 Markdown 概念网络
        │
        ▼
SKILL.md + CLAUDE.md       人与 Agent 共同维护的工作规约
```

## 📁 项目结构

```text
mneme/
├── skills/mneme/          # 唯一交付物（skill.sh layout）
│   ├── SKILL.md           # Agent 工作流与触发说明
│   ├── scripts/
│   │   ├── mneme.py       # CLI 入口 shim
│   │   └── mneme/         # Python 包（okflib / indexlib / lazy_index / ...）
│   └── references/        # ingest / query / lint / 索引规范
├── sample-bundle/         # OKF 合规示范与测试夹具
├── tests/                 # 143 条分层测试 + 发布门禁
├── .research/             # 上游规范与设计依据
├── docs/superpowers/      # specs / plans / reports
├── dist/                  # 构建产物（mneme-*.whl；gitignored）
└── CLAUDE.md              # 项目宪法与维护规约
```

## 🪶 零依赖 OKF 核心

`mneme` 的 L1（lint / init / ingest / query）只依赖 Python 标准库：

| 能力 | 依赖 |
|---|---|
| `init` 脚手架 | stdlib (`pathlib`, `argparse`) |
| `lint` OKF 校验 | stdlib + 手写 TOML writer（`toml_writer.py`，~60 行） |
| `ingest` 蒸馏流程 | stdlib + host agent 的 Read/Write/Edit 工具 |
| `query` 检索综合 | stdlib + host agent |
| `reindex` / `search`（L2） | 懒装 `sqlite-vec` + `fastembed`（仅首次需要） |

严格 YAML 校验需要 `PyYAML`（可选 extras `pip install 'mneme[validate]'`）。默认安装走手写子集解析器 + WARN，不破坏容错消费契约。

## 🏷️ 标签

`mneme` 的语义标签（OKF type vocab 推荐）：

- `Concept` — 概念 / topic 页面
- `Reference` — 蒸馏的外部资料（论文 / 文章 / 文档）
- `Summary` — 跨概念的综合
- `Source` — `sources/` 里的原始资料（不可变）

OKF 协议 v0.1 容错：未知 type 只告警，不断言失败。

## 🤝 朋友项目

想把一次塔罗解读沉淀成长期可回看的个人反思记录？试试 [塔罗树洞](https://github.com/Scott1743/tarot-confessional)：它负责温柔地完成抽牌与象征性解读，Mneme 负责把有价值的体会整理进本地知识 Wiki。两者都坚持本地优先、Agent 驱动和可检查的开放文件。

## 🧑‍💻 开发者指南

```bash
pip install -e '.[dev]'
pytest                          # 143 passed
pytest -m 'network or compat'   # 跑 L2 模型下载 + 1.0.x wheel 兼容 smoke
python -m build --wheel         # 构 wheel → dist/mneme-1.1.0-py3-none-any.whl
```

涉及 OKF 合规性的修改，请先阅读 [上游规范](.research/upstream/OKF-SPEC.md) 与 [约束摘要](.research/constraints.md)。`.research/upstream/` 保存的是只读的上游原文副本。

详细的设计与实施计划：`docs/superpowers/plans/2026-07-13-mneme-1.1.0-implementation.md`。

## 📜 许可证

本项目采用 [MIT License](LICENSE)。

---

<div align="center">

**让知识留在你手里，也让每次阅读都成为下一次思考的起点。**

</div>