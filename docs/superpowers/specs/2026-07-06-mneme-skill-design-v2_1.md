# Mneme Skill — Design Spec v2.1

- **Date:** 2026-07-06
- **Status:** Draft — awaiting user review
- **Supersedes:** `2026-07-06-mneme-skill-design-v2.md` (v2)
- **Why:** v2 introduced independent Strands agents (`ingest.py`/`query.py`/`lint.py` + `tools.py`). They are removed: **all write paths flow through the SKILL.md-driven host Claude**, not an independent agent runtime. The L2 (sqlite-vec + fastembed) stays — it solves the context-overflow problem. CLI is thinned to `init` + `reindex` only.
- **Research basis:** gbrain dream cycle (auto-curation on a schedule, no user interaction, `dream-report-<date>.md` audit), Karpathy LLM Wiki, OKF v0.1, Strands SDK (no longer used at runtime; referenced only as design context).

## 1. 目标与身份

mneme 是一个**轻量化、本地优先**的 LLM wiki，以 **Claude Code skill 为唯一入口**，继承 Karpathy *LLM Wiki* 思想、服从 OKF v0.1。

**核心修订（v2 → v2.1）：** 移除所有独立 agent runtime。Host Claude 在加载 `SKILL.md` 后，按章节引导直接做事——用 `Read`/`Write`/`Edit`/`Bash`/`Glob`/`Grep` 等原生工具调 `okflib`/`indexlib`/`mneme.py`。不再有 Strands `@tool` 装饰器、不再有独立 agent 进程。

**轻量化理念：** 嵌入式存储（sqlite-vec）、按需执行（无常驻服务）、CLI 只 2 个子命令（init/reindex）。L2 索引解决 wiki 超出上下文的问题；host Claude 解决"语义判断"问题。

## 2. 关键决策

| # | 决策点 | 选择 |
|---|---|---|
| D1 | wiki 位置 | 外部 bundle + 便携 skill |
| D2 | 内容域 | 研究/学习笔记；type: Concept / Reference / Summary / Source |
| D3 | 分层 | L1 wiki (OKF bundle + `okflib`) + L2 index (`indexlib`：sqlite-vec + fastembed)。**无 L3 独立 agent 层** |
| D4 | 位置持久化 | `~/.config/mneme/config.toml` + 用户级 skill |
| D5 | L2 索引存储 | sqlite-vec（嵌入式），`<bundle>/.mneme/index.db` |
| D6 | embedding 生成 | 本地 fastembed (ONNX) 多语种小模型，默认 `intfloat/multilingual-e5-small` (384-dim)；离线、China 网络安全 |
| D7 | 引擎 | **宿主 agent**（任何遵循 skill 协议的 LLM agent runtime — Claude Code / Codex CLI / Cursor / 其他 — 加载 mneme skill 后按 SKILL.md 引导做事） |
| D8 | 链入 | **SKILL.md 是唯一入口**；CLI 只保留 `init` 和 `reindex`（手动/脚本/CI 用） |
| D9 | dream | 自动定时任务，**host Claude 跑 SKILL.md 的 dream 章节**；全套 git 保险 |

## 3. 架构（v2.1）

```
┌──────────────────────────────────────────────────────────┐
│  宿主 agent（Claude Code / Codex CLI / Cursor / 其他）   │
│  ├─ 加载 skills/mneme/SKILL.md → 按章节引导做事       │
│  └─ 用原生工具调：                                       │
│     ├─ Bash → mneme.py init / mneme.py reindex         │
│     ├─ Read / Write / Edit → 直接改 .md 文件            │
│     └─ Bash → indexlib / okflib（作为 Python module）   │
└──────────────────────────────────────────────────────────┘
                         ↓
┌──────────────────────────────────────────────────────────┐
│  skills/mneme/scripts/                                   │
│  ├─ okflib.py       OKF 解析/校验/列举（零依赖）        │
│  ├─ indexlib.py     sqlite-vec + fastembed + chunk/      │
│  │                 upsert/remove/search/reindex          │
│  ├─ validate_okf.py okflib 的 CLI 前端                  │
│  └─ mneme.py        CLI：init / reindex                  │
└──────────────────────────────────────────────────────────┘
                         ↓
┌──────────────────────────────────────────────────────────┐
│  <bundle>/                                              │
│  ├─ index.md / log.md / sources/ / concepts/ / ...      │
│  └─ .mneme/index.db    L2 索引（gitignored）            │
└──────────────────────────────────────────────────────────┘
```

**没有独立的 agent runtime、Strands `@tool` 装饰器、MCP server、后台 daemon。宿主 agent 即接口——任何遵循 skill 协议的 LLM agent runtime 都能驱动 mneme。**

## 4. SKILL.md 接口（宿主 agent 加载后看到的引导）

6 个场景章节，每个章节是一段 prose，引导宿主 agent 用原生工具（Read/Write/Edit/Bash/Glob/Grep）做事。宿主 agent 不绑定特定产品——任何遵循 skill 协议的 LLM agent runtime 都适用：

### 4.1 `init <path>`
- 引导 host Claude 跑 `Bash: mneme.py init <path> [--config <config>]` 创建 OKF 骨架
- 验证：`<path>/index.md` 含 `okf_version`，`<path>/log.md` 与 `sources/.gitkeep` 存在
- 写 `bundle_path = "<path>"` 到 `~/.config/mneme/config.toml`

### 4.2 `reindex [--config <config>]`
- 引导 host Claude 跑 `Bash: mneme.py reindex`（全量 reindex，扫所有概念页 → sqlite-vec）
- 输出：indexed N concepts into `<bundle>/.mneme/index.db`

### 4.3 `ingest <source path>`
- 引导宿主 agent：
  1. `Read <source path>` → 拿全文
  2. `Bash: python -c "from indexlib import chunk_markdown; ..."` 决定怎么拆概念（宿主 agent 用自己的判断拆）
  3. 对每个概念：`Write` 写 `<bundle>/concepts/<slug>.md`（含 frontmatter: type/title/description/tags/timestamp/resource）
  4. `Edit <bundle>/index.md` 加 `* [Title](path) - description`
  5. `Edit <bundle>/log.md` 追加 `## YYYY-MM-DD ingest | <title>`
  6. `Bash: mneme.py reindex` 重 build L2

### 4.4 `query <question>`
- 引导宿主 agent：
  1. 调 `Bash: python -c "from indexlib import search, open_index, default_embed_fn; ..."` 拿 top-k=10
  2. 读相关概念页：`Read <bundle>/concepts/<id>.md`
  3. 宿主 agent 自己综合答案 + 内联引用（`/concepts/<id>.md` 形式）
  - **朴素 RAG**：检索 + 拼 prompt + 宿主 agent 综合。**不开独立 agent。**

### 4.5 `lint`
- 引导宿主 agent：
  1. `Bash: mneme.py reindex --validate`（或 `validate_okf.py`）
  2. `Bash: python -c "from okflib import find_orphans, list_concepts; ..."` 找孤儿
  3. 宿主 agent 自己看页内容：矛盾 / 过时 / 缺交叉链
  4. 写策展报告（不必直接改文件，由你决定）

### 4.6 `dream` （定时任务，**全自动**）

详见 §6。核心是 git 保险 + 自动策展循环。

## 5. mneme.py CLI（最终）

```bash
mneme init <path> [--config <cfg>]    # scaffold OKF bundle + write config
mneme reindex [--config <cfg>]       # full L2 rebuild
mneme --help
```

**没了** ingest/query/lint 子命令（这些走 SKILL.md）。其它子命令也一律不暴露——保持 CLI 极简。

## 6. dream 周期（核心新增）

### 6.1 触发

```cron
# 用户 crontab（举例：每晚 3 点）—— 任何能加载 skill 的 agent runtime 都行
0 3 * * * cd <bundle> && <agent-runtime> --skill mneme "运行 dream 周期"
```

或宿主 agent 的 scheduler hook / LaunchAgent / systemd timer / 手动 `mneme dream`。

### 6.2 工作流（宿主 agent 加载 mneme skill 后按 SKILL.md dream 章节执行）

**前 guard**：

1. `Bash: git rev-parse --git-dir`（如果 `<bundle>/.git` 不存在 → 优雅降级：dream 不做 git 操作，但仍跑策展，写报告；不报错）
2. 如是 git 仓库：`Bash: git add -A && git commit -m "pre-dream $(date +%Y-%m-%dT%H:%M)" --allow-empty`

**核心循环**（≤ `max_dream_changes_per_run=20` 默认；可调）：

| 动作 | 用法 |
|---|---|
| 合并重复 | `Bash: python` 调用 indexlib 找 `search(... k=20)` 后相似度 ≥ 0.92 的对 → host Claude 决定合并目标 → `Write` 新合并页 + `Edit` redirect 旧链接 |
| 归档孤儿 | `Bash: python` 调 `okflib.find_orphans` → host Claude 判断（`timestamp > 90d` 且无 log 引用 → 移到 `archive/`）→ `Bash: mv` + `Edit log.md` |
| 补交叉链 | 找内容相似但无链接的概念对 → `Edit` 加 `[/concepts/other.md](/concepts/other.md)` |
| 建 Summary | 同一话题 ≥ 5 个 concepts → `Write` 新 Summary 页 + `Edit index.md` |
| 重新 reindex | `Bash: mneme.py reindex` |

**每改一处**先写到 `<bundle>/.mneme/dream-pending/` 暂存，最后一次性 `Bash: mv` 到目标位置（事务性）。

**后 guard**：

1. `Bash: mneme.py reindex`（重新 build L2 索引反映新结构）
2. `Bash: validate_okf.py <bundle>` —— 必须 0 ERROR

**报告**（写到 `<bundle>/dream-report-<date>.md`）：

```
# dream report — 2026-07-07

## 本轮改动 (N=12, 上限 20)
1. 合并 concepts/foo.md + concepts/bar.md → concepts/foo.md (reason: 0.94 similarity, 重复定义 Attention)
2. 归档 concepts/old-note.md → archive/2025/old-note.md (reason: 245d old, 无引用)
3. ...

## 校验结果
- validate: 0 ERROR / 3 WARN
- index: 142 → 141 concepts (合并 -1, 归档 -0 after reindex)

## git 状态
- pre-dream snapshot: abc1234
- 本轮 commit: def5678 (branch: dream/2026-07-07)

## 不满意？
git revert HEAD          # 撤销本轮 dream
git checkout abc1234 -- . # 仅撤销文件改动，保留 commit
```

**git 提交**（如是 git 仓库）：`git add -A && git commit -m "dream: <date>"`，建议推到 `dream/<date>` 分支（host Claude 不直接 push，由你 review 后手动 merge）。

### 6.3 软上限

`max_dream_changes_per_run = 20`（可调）。若待改动 > 20：
- dream 报告里说"还有 N 个待批"
- 只做前 20 个最确定的（合并、归档优先；建 Summary、补交叉链延后）
- 防止"模型抽风"

## 7. 仓库布局（v2.1）

```
skills/mneme/
├── SKILL.md                # 重写：6 场景章节（init/reindex/ingest/query/lint/dream），引导 host Claude
├── scripts/
│   ├── okflib.py           # 保留
│   ├── validate_okf.py     # 保留
│   ├── indexlib.py         # 保留
│   └── mneme.py            # 简化：只 init + reindex 两个子命令
└── references/             # 保留
    ├── workflow-ingest.md  # 修订：不再描述"调 mneme ingest"，改为"host Claude 走 SKILL.md ingest 章节"
    ├── workflow-query.md   # 同上
    ├── workflow-lint.md    # 同上
    ├── type-vocab.md
    ├── wiki-structure.md
    └── index-design.md
```

**删除**：`tools.py`、`ingest.py`、`query.py`、`lint.py` + `tests/test_tools.py`、`tests/test_agents_smoke.py`、`tests/test_cli.py`（v2 的 cli 测试假设有 ingest/query/lint；v2.1 没有这些子命令）、`pyproject.toml` 的 `[agents]` extras。

## 8. 测试（TDD）

| 测试 | 保留？ |
|---|---|
| `tests/test_okflib.py` | ✅ 保留 |
| `tests/test_indexlib.py` | ✅ 保留 |
| `tests/test_integration.py` | ✅ 保留 |
| `tests/test_tools.py` | ❌ 删除（tools.py 删了） |
| `tests/test_agents_smoke.py` | ❌ 删除（无独立 agent） |
| `tests/test_cli.py` | ❌ 删除（CLI 只有 init/reindex，v2 的 cli 测试已过期；改写为 init+reindex 的 TDD 测试） |

## 9. 非目标（v2.1）

- ❌ 独立 agent runtime（Strands / LangChain / CrewAI 等）—— 一律走 SKILL.md + host Claude
- ❌ `@tool` 装饰器 —— host Claude 用原生工具
- ❌ MCP server —— CLI+skill 已覆盖；按需再加
- ❌ v2 converters（Word/PDF/PPT/Excel/图片/HTML → md/csv）—— 仍 deferred
- ❌ query 自动回填 —— 提议，不自动写
- ❌ dream push 到远端 —— 仅本地 commit，由你 push / merge
- ❌ dream 自动归档高访问但低内容页 —— 保守策略，不动高访问页

## 10. 从 v2 迁移

- 删除 `tools.py`、`ingest.py`、`query.py`、`lint.py`
- 删除 `pyproject.toml` 的 `[agents]` extras（保留 `[index]`、`[dev]`、`[all]`）
- 删除 `tests/test_tools.py`、`tests/test_agents_smoke.py`、`tests/test_cli.py`（v2 版）；新增 `tests/test_cli.py` 测 init+reindex
- 重写 `SKILL.md`：6 场景，host Claude 直接做事（不调 CLI 中转）
- 重写 `references/workflow-{ingest,query,lint}.md`：描述 host Claude 怎么用 skill 工具做
- `mneme.py` 简化：删 cmd_ingest/query/lint，保留 init+reindex
- v2 spec、v2 plan 保留为历史（`docs/superpowers/specs/2026-07-06-mneme-skill-design-v2.md`）

## 11. 未来

- **v2.2 converters**：薄封装 mammoth/pdfplumber/python-pptx/openpyxl/pytesseract/trafilatura，lazy import + `mneme[converters]` extras
- **dream 可配置策略**：低/中/高保守度（高保守度 = dream 只出报告）
- **MCP server**（按需）：跨客户端共享时再加
- **远程 L2**（按需）：多机共享时再换 Supabase/pgvector