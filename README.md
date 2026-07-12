<div align="center">

# Mneme · 轻量化 LLM Wiki

**一个生于本地文件系统、由 Agent 增量维护的 OKF 知识 Wiki**

*把读过的东西编译一次，让知识在每次使用中继续复利。*

[![MIT License](https://img.shields.io/badge/license-MIT-6f42c1.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-1.0.0-0f766e.svg)](CHANGELOG.md)
[![OKF](https://img.shields.io/badge/OKF-v0.1-2563eb.svg)](.research/upstream/OKF-SPEC.md)
[![Skills.sh](https://img.shields.io/badge/skills.sh-mneme-111827.svg)](https://skills.sh/?q=mneme)

</div>

---

## ✨ 为什么选择 Mneme？

多数知识工具让模型每次都从头检索、重新理解。Mneme 换了一种思路：让 Agent 像维护源码一样，把原始资料逐步编译成互相链接的 Markdown 概念页。

- **本地优先**：知识留在普通文件和 Git 仓库里
- **增量维护**：一次摄入，多次查询，持续修订
- **开放格式**：遵循 Google OKF v0.1，Markdown + YAML 即可互通
- **零常驻服务**：没有数据库服务、云端后台或专用运行时
- **Git 原生**：知识可以 diff、branch、review 和 blame

## 🚀 快速开始

### 方式一：通过 skills.sh 安装（推荐）

```bash
npx skills add Scott1743/mneme
```

### 方式二：从 GitHub 安装

```bash
git clone https://github.com/Scott1743/mneme.git
cd mneme
python3 -m pip install -e .
```

把 `skills/mneme` 安装或链接到你的 Agent skills 目录后，就可以直接说：

```text
用 mneme 初始化一个 wiki，然后把这份研究笔记摄入进去。
```

## 🧠 核心能力

### Ingest · 摄入

保留不可变的原始资料，再把其中的知识蒸馏为可互链、可追溯的概念页，同时更新索引、时间线与本地语义索引。

### Query · 查询

先定位相关概念，再读取权威 Markdown 页面进行综合回答，并用 bundle 内链接标明依据。

### Lint · 体检

检查 OKF 硬约束、孤儿页、断链和策展问题；未知类型与可选字段缺失只告警，不破坏容错消费。

### Search · 检索

在资料规模增长后，按需启用 sqlite-vec + FastEmbed 的 L2 本地索引；Wiki 本体始终是可直接读取的 Markdown。

## 🏛️ 三层架构

```text
原始资料 sources/          不可变的事实来源
        │
        ▼
OKF Wiki                  Agent 维护的 Markdown 概念网络
        │
        ▼
AGENTS.md + SKILL.md      人与 Agent 共同维护的工作规约
```

## 📁 项目结构

```text
mneme/
├── skills/mneme/          # 可直接安装的 Agent Skill
│   ├── SKILL.md           # 工作流与触发说明
│   └── references/        # ingest / query / lint / 索引规范
├── src/mneme/             # 零依赖 L1 与可选 L2 CLI
├── sample-bundle/         # OKF 合规示范与测试夹具
├── tests/                 # 分层测试与发布门禁
├── .research/             # 上游规范与设计依据
└── AGENTS.md              # 项目宪法与维护规约
```

## 🤝 朋友项目

想把一次塔罗解读沉淀成长期可回看的个人反思记录？试试 [塔罗树洞](https://github.com/Scott1743/tarot-confessional)：它负责温柔地完成抽牌与象征性解读，Mneme 负责把有价值的体会整理进本地知识 Wiki。两者都坚持本地优先、Agent 驱动和可检查的开放文件。

## 🧑‍💻 开发者指南

```bash
python3 -m pip install -e '.[dev]'
python3 -m pytest
```

涉及 OKF 合规性的修改，请先阅读 [上游规范](.research/upstream/OKF-SPEC.md) 与 [约束摘要](.research/constraints.md)。`.research/upstream/` 保存的是只读的上游原文副本。

## 📜 许可证

本项目采用 [MIT License](LICENSE)。

---

<div align="center">

**让知识留在你手里，也让每次阅读都成为下一次思考的起点。**

</div>
