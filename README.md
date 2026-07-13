<div align="center">

# Mneme · 轻量化 LLM Wiki

**一个生于本地文件系统、由 Agent 增量维护的 OKF 知识 Wiki**

*把读过的东西编译一次，让知识在每次使用中继续复利。*

[![MIT License](https://img.shields.io/badge/license-MIT-6f42c1.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-1.1.0-0f766e.svg)](CHANGELOG.md)
[![OKF](https://img.shields.io/badge/OKF-v0.1-2563eb.svg)](.research/upstream/OKF-SPEC.md)
[![skills.sh](https://skills.sh/b/Scott1743/mneme)](https://skills.sh/Scott1743/mneme)
[![Python](https://img.shields.io/badge/python-%E2%89%A53.11-3776ab.svg)](.research/upstream/OKF-SPEC.md)
[![Zero--dep core](https://img.shields.io/badge/OKF_core-zero_deps-22c55e.svg)](#-零依赖-okf-核心)

[`npx skills add Scott1743/mneme`](https://skills.sh/Scott1743/mneme) · [GitHub release .zip](https://github.com/Scott1743/mneme/releases/latest)

</div>

<div align="center">

📖 完整图文介绍页：**[https://scott1743.github.io/mneme/](https://scott1743.github.io/mneme/)**（产品初衷 + 安装 + 原理）

</div>

---

## ✨ 为什么选择 Mneme？

多数知识工具让模型每次都从头检索、重新理解。Mneme 换了一种思路：让 Agent 像维护源码一样，把原始资料逐步编译成互相链接的 Markdown 概念页。

- **本地优先**：知识留在普通文件和 Git 仓库里
- **零常驻服务**：没有数据库服务、云端后台或专用运行时
- **零依赖核心**：L1（lint / init / ingest / query）只跑在 Python 标准库上
- **开放格式**：遵循 Google OKF v0.1，Markdown + YAML 即可互通
- **Git 原生**：知识可以 diff、branch、review 和 blame
- **轻量分发**：一个 zip 包——下载、解压、丢进 skills 目录、立刻能用

## 🚀 安装

`mneme` 的发布物**只有一个**：`dist/mneme-<version>.zip`。下载、解压、把它放到你的 agent 的 skills 目录里，就完事了。

### 方式一：通过 skill.sh（推荐）

```bash
npx skills add Scott1743/mneme
```

落地到 `~/.claude/skills/mneme/`，agent 立刻识别。

### 方式二：手动下载 zip

1. 从 [GitHub Releases](https://github.com/Scott1743/mneme/releases/latest) 下载 `mneme-1.1.0.zip`
2. 解压：`unzip mneme-1.1.0.zip`
3. 把解压出来的 `mneme/` 目录放到 agent 的 skills 目录：

```bash
# Claude Code:
mv mneme ~/.claude/skills/mneme
```

4. agent 立刻就能识别。**没有 pip install、没有 wheel、没有 `pip install mneme`，没有任何额外步骤。**

> 为什么是 zip 而不是 wheel / `pip install mneme`？skill 本身就是一组文件。wheel 是 Python 库的分发格式，需要 site-packages 才能跑——跟 agent skill 的工作方式完全不匹配。一个 zip 直接对应 `~/.claude/skills/<name>/` 目录，语义清晰、对用户透明。

## 调用

skill 装好后，agent 通过本地 CLI 调用：

```bash
python3 ~/.claude/skills/mneme/scripts/mneme.py init <path>
python3 ~/.claude/skills/mneme/scripts/mneme.py lint <bundle>
python3 ~/.claude/skills/mneme/scripts/mneme.py reindex --config <cfg>
python3 ~/.claude/skills/mneme/scripts/mneme.py search "<query>" --json -k 10
```

四个子命令完整覆盖 OKF v0.1 wiki 的生命周期。

## 🧠 核心能力

### Ingest · 摄入

保留不可变的原始资料（自动复制到 `<bundle>/sources/`），再把其中的知识蒸馏为可互链、可追溯的概念页，同时更新 `index.md`（按 type 分 section）、`log.md`（newest-first 顶部插入）。

### Query · 查询

先定位相关概念，再读取权威 Markdown 页面进行综合回答，并用 bundle 内链接标明依据。

### Lint · 体检

检查 OKF v0.1 硬约束（frontmatter 必填 `type`、保留文件结构、YAML 严格校验）、孤儿页、断链和策展问题；未知类型与可选字段缺失只告警，不破坏容错消费契约（OKF §9）。

### Search · 检索（可选）

`init` / `lint` / `ingest` / `query` 都不需要任何第三方包——纯 stdlib 就跑。**`search` 和 `reindex` 是 L2 增强功能**，依赖 `sqlite-vec` 和 `fastembed`，**需要时再装一次就好**：

```bash
pip install 'sqlite-vec>=0.1.9,<0.2' 'fastembed>=0.8.0,<0.9'
```

装完一次就不用再管了，模型会缓存到本地。**没有自动安装、没有 surprise 网络调用——用户决定装还是不装。**

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
├── skills/mneme/          # 唯一交付物（直接打成 zip）
│   ├── SKILL.md           # Agent 工作流与触发说明
│   ├── scripts/
│   │   ├── mneme.py       # CLI 入口 shim
│   │   └── mneme/         # Python 包（okflib / indexlib / config / toml_writer / ...）
│   └── references/        # ingest / query / lint / 索引规范
├── sample-bundle/         # OKF 合规示范与测试夹具
├── tests/                 # 151 条分层测试 + 发布门禁
├── .research/             # 上游规范与设计依据
├── docs/superpowers/      # specs / plans / reports
├── dist/mneme-*.zip       # 发布物（gitignored）
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
| `reindex` / `search`（L2，可选） | 用户自行 `pip install sqlite-vec fastembed` |

`pyproject.toml` 只剩 `[tool.pytest]` 配置——**没有 `[project]`、没有 `[build-system]`、没有 setuptools/wheel**。zip 是唯一分发物。

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
pip install pytest
pytest                          # 151 passed
pytest -m network               # L2 检索（需要 sqlite-vec + fastembed）
```

涉及 OKF 合规性的修改，请先阅读 [上游规范](.research/upstream/OKF-SPEC.md) 与 [约束摘要](.research/constraints.md)。`.research/upstream/` 保存的是只读的上游原文副本。

构 zip：

```bash
python3 -c "
import zipfile
from pathlib import Path
ROOT = Path('.')
src = ROOT / 'skills' / 'mneme'
out = ROOT / 'dist' / 'mneme-1.1.0.zip'
with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
    for path in sorted(src.rglob('*')):
        if path.is_file() and '__pycache__' not in path.parts:
            zf.write(path, 'mneme/' + str(path.relative_to(src)))
"
```

## 📜 许可证

本项目采用 [MIT License](LICENSE)。

---

<div align="center">

**让知识留在你手里，也让每次阅读都成为下一次思考的起点。**

</div>