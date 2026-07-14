# Mneme

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-3.0.0-blue.svg)](https://github.com/Scott1743/mneme/releases/tag/v3.0.0)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776ab.svg)](.research/upstream/OKF-SPEC.md)
[![skills.sh](https://skills.sh/Scott1743/mneme.svg)](https://skills.sh/Scott1743/mneme)

> 一座由 Agent 增量维护的本地 Markdown 知识库。
> **dream** 写，**search** 读——其余都是细节。

`dream` 把读过的资料编译进一棵你可以反复行走的本地概念树。
`search` 在你的 wiki 里走，按 `index.md` / tags / 链接走；wiki 大的时候打开本地 SQLite FTS5 加速召回。找不到就明说，不编。

## 安装

一行命令，从 [skill.sh](https://skill.sh/Scott1743/mneme)：

```bash
npx skills add Scott1743/mneme
```

落地到 `~/.claude/skills/mneme/`，重启 agent 会话即可。**没有 wheel、没有 `pip install` 全包、没有 setuptools——一个 zip，解压即用。**

固定安装零依赖基础版： [v2.0.0 skill zip](https://github.com/Scott1743/mneme/releases/download/v2.0.0/mneme-2.0.0.zip)。最新版语义版： [v3.0.0 skill zip](https://github.com/Scott1743/mneme/releases/download/v3.0.0/mneme-3.0.0.zip)。

**更多**：图文版介绍（产品初衷 + 娓娓道来 + 安装示例）见仓库内 [`introduction/index.html`](introduction/index.html)，下载后可在浏览器中离线阅读。本地预览：

```bash
cd introduction && python -m http.server 8000
# 然后浏览器打开 http://localhost:8000/
```

或等 GitHub Pages 启用后访问 `https://scott1743.github.io/mneme/`（仓库 Settings → Pages → Source = GitHub Actions）。

## 两件事（用户表面）

- **dream** —— 你丢资料进来，agent 写成 OKF 概念页，加 tag、互相链接，更新 `index.md` 与 `log.md`。默认先出预览，等你点头才落盘。
- **search** —— 你问问题，agent 在你的 wiki 里走。默认按 `index.md` / tags / 链接 / grep 走；wiki 大的时候按 L1（SQLite FTS5）召回。最终答案由 agent 读完整页面综合，引用是 bundle 内路径。

`init` / `lint` / `reindex` / `dream` 是 agent 在后台跑的确定性脚本，不出现在用户叙事里。v3.0 可通过 `--l2` 显式启用语义召回；索引永远可删除。

### 夜巡 `dream`（可选）

想要每天夜里自动跑一次只读审计？`mneme dream --schedule` 只**打印**一段你系统调度器能直接吃的片段——macOS 的 launchd plist、Linux 的 crontab、Windows 的 `schtasks` 行；不会自己装。
默认凌晨 `02:00`，改时间加 `--time HH:MM`，想撤就 `mneme dream --unschedule`。一行粘贴、即可。

## 4 层架构

```
原始资料 sources/      不可变事实来源；agent 只读不改
        │
        ▼
OKF Wiki                唯一真相源；agent 完全维护
                        （type 描述角色 / tags 描述主题 / 链接表达关系）
        │
        ▼
Agent Skill             告诉 agent 怎么维护、怎么查询
                        （SKILL.md + references/）
        │
        ▼
Disposable accelerator  可删除的导航缓存（wiki 大时打开 FTS5；不可信源）
```

`type` 描述文档角色（OKF v0.1 协议级 MUST），`tags` 描述主题归类（mneme 写作纪律——我们写的概念页至少 1 个 tag，消费外部 OKF 时缺 tag 只 WARN），Markdown 链接表达具体关系。三者语义不重叠。

## L1 默认 —— sqlite3 + FTS5

`L1` 是 mneme 的默认导航层：Python 内建 `sqlite3` + FTS5，零依赖。索引文件 `<bundle>/.mneme/index.db`，是 **disposable accelerator**，永远不是事实来源——删掉它仍能 `git log` 出 wiki 的全部真相。

```bash
mneme reindex       # 全量重建一次；幂等
mneme search "X"    # FTS5 候选 + snippet；agent 读完整页综合
```

## 可选 L2（v3.0）

默认仍是 FTS5。需要语义召回时，在用户自行安装 `sqlite-vec` 与 `FastEmbed` 后，显式使用 `reindex --l2` / `search --l2`；不会自动安装或静默回退。

## OKF v0.1 + tags 写作纪律

- **OKF v0.1**（MIT，2026-06-12）—— YAML frontmatter 必填 `type`，容错消费契约：缺可选字段、未知 `type`、未知额外 frontmatter 键、断链、缺 `index.md` **只 WARN**。
- **mneme 写作纪律** —— 我们自己写出来的概念页至少要有 1 个 `tags`；消费外部 OKF bundle 时缺 tags 只 WARN。
- **Topic 页面** —— 需要时写一份普通 OKF `Topic` 页面，不用 `tags/<tag>.md` 镜像聚合；前者维护成本低、不容易腐化。

完整规范见 [`.research/upstream/OKF-SPEC.md`](.research/upstream/OKF-SPEC.md) —— 上游原文的 verbatim MIT 副本，不允许改动。

## 项目结构

```text
skills/mneme/               ← 唯一交付物（打成 zip）
├── SKILL.md                ←   agent 工作流（dream + search）
├── scripts/mneme.py        ←   CLI 入口 shim
├── scripts/mneme/          ←   Python 包（cli / okflib / indexlib / config；stdlib only）
└── references/             ←   工作流文档（按需加载）
sample-bundle/              ←   OKF 合规示范 + 测试夹具
tests/                      ←   分层测试
introduction/               ←   GitHub Pages 介绍页（自包含 HTML）
.research/                  ←   上游规范 + 立项研究
docs/superpowers/           ←   specs + plans + reports
```

## 开发者

```bash
pip install pytest
pytest                          # 离线分层测试
python scripts/build_zip.py     # 产 dist/mneme-3.0.0.zip
```

L2（语义召回）是 v3.0 的显式可选路径；默认 FTS5 不引入相关依赖。CI 在 Python 3.11 / 3.12 / 3.13 三档矩阵上跑。

## 朋友项目

森林密语 / 塔罗树洞：[github.com/Scott1743/tarot-confessional](https://github.com/Scott1743/tarot-confessional) —— 同源、本地优先、Agent 驱动的个人反思记录。

---

[MIT License](LICENSE) · 本仓库由 Agent 维护 · 让知识留在你手里。
