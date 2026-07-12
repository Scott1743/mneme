# Mneme 测试方案 Plan

**立项日期**: 2026-07-12  
**作者**: scott1743 (with TRAE agent)  
**状态**: Draft, awaiting approval  
**前置条件**: 1.0.0 release gate 已闭合(commit `9692f41`),141 个测试全过

---

## 1. 背景与动机

1.0.0 闭合后,mneme 已有 **18 个测试文件 / 约 140 个测试函数**,但只通过 `pytest` 一键跑全部。这带来三个具体痛点:

1. **反馈慢**:开发者改一个 okflib 函数,要等 60+ 秒跑完所有 e2e + 黑盒才能确认没回归,而真正相关的 unit 测试只要 1 秒。
2. **网络敏感测试混在一起**:`test_retrieval_bench.py` / `test_e2e_ingest.py` / `test_e2e_query.py` 触发 HuggingFace 模型下载,在 AGENTS.md §8 描述的网络受限环境会拖慢或 skip,但开发者无法显式跳过它们。
3. **无覆盖率测量**:1.0.0 release gate 闭合靠"测试数量 + 全绿",没有 `src/mneme/` 各模块的覆盖率基线,新增代码可能没测试就合入。

本方案在**不动测试逻辑**的前提下,把现有测试按层标记、按场景运行,并加 coverage 测量与一份对外可读的 TESTING.md。

## 2. 设计原则

- **不重写测试**:只加 marker、调整 pyproject.toml、加 helper 脚本。任何"测试本身有 bug"另开 issue,不混入本方案。
- **分层对齐 Karpathy 三层架构**:L1 (okflib) / L2 (indexlib) / E2E (CLI + bundle) / Release-gate / Docs,与 AGENTS.md 的分层依赖一致。
- **离线优先**:默认 `pytest` 跑离线能跑的全部,网络敏感测试必须显式 opt-in。
- **覆盖率是观察,不是门槛**:先建立基线,不设 fail-under 阈值,避免 1.0.x 维护期被硬阈值卡住合入。

## 3. 测试分层与 marker

### 3.1 marker 定义

在 `pyproject.toml` 的 `[tool.pytest.ini_options]` 注册 6 个 marker:

| marker | 含义 | 离线可跑 | 典型耗时 |
|---|---|---|---|
| `unit` | 单函数/单模块的纯逻辑测试,无外部 IO | ✅ | <1s |
| `integration` | 跨模块组合,但仍进程内 + 无网络 | ✅ | 1-3s |
| `e2e` | 通过 CLI subprocess 跑完整 bundle 流程 | ⚠️ 部分 | 5-30s |
| `release` | 发布门禁:wheel / 入口 / 版本 / 预算 / 漂移 | ✅ | 3-10s |
| `docs` | 文档冻结规则 | ✅ | <1s |
| `network` | 需要访问 HuggingFace 下载模型 | ❌ | 30-90s |

### 3.2 现有 18 个文件的 marker 分配

| 文件 | 主 marker | 次 marker | 备注 |
|---|---|---|---|
| `test_okflib.py` | `unit` | — | 39 函数,纯 stdlib |
| `test_tools_helpers.py` | `unit` | — | |
| `test_config.py` | `unit` | — | |
| `test_cli.py` | `unit` | — | monkeypatch,不走真实 indexlib |
| `test_indexlib.py` | `unit` | — | skip-if-missing sqlite-vec |
| `test_integration.py` | `integration` | — | skip-if-missing sqlite-vec |
| `test_e2e_ingest.py` | `e2e` | `network` | subprocess reindex 走真实模型 |
| `test_e2e_lint.py` | `e2e` | — | 纯文件,无网络 |
| `test_e2e_query.py` | `e2e` | `network` | subprocess reindex |
| `test_retrieval_bench.py` | `e2e` | `network` | 外部语料 + 模型 |
| `test_blackbox_news.py` | `e2e` | — | keyword embedder,离线 |
| `test_install.py` | `release` | — | 10 函数,仅 extras 测试需网络 |
| `test_entrypoint.py` | `release` | — | |
| `test_version.py` | `release` | — | |
| `test_release_budget.py` | `release` | — | |
| `test_skill_drift.py` | `release` | — | |
| `test_skill_text.py` | `docs` | — | |
| `test_docs.py` | `docs` | — | |

`test_install.py::test_wheel_install_with_extras_reindex_runs` 单独再打 `network` marker(文件级 `release`,函数级叠加 `network`)。

## 4. 运行策略

### 4.1 三档运行命令

提供 `Makefile` + 文档化的 pytest 命令,对应三种反馈场景:

| 档位 | 命令 | 用途 | 预期耗时 |
|---|---|---|---|
| **fast** | `make test-fast` 或 `pytest -m "unit"` | 改一个函数后秒级反馈 | ~1s |
| **default** | `pytest`(默认) | 本地提交前 | ~10s(跳过 network) |
| **full** | `make test-full` 或 `pytest -m ""`(含 network) | release 前完整验证 | 60-90s |

**关键设计**:`pytest` 不带任何 `-m` 时,通过 `pyproject.toml` 的 `addopts = "-m 'not network'"` 默认跳过 network 测试。开发者想跑全部时显式 `pytest -m ""` 覆盖。

### 4.2 CI 矩阵调整

`.github/workflows/ci.yml` 已有 8 cell 矩阵 + wheel smoke。本方案在 `Run pytest` 步骤前加两步:

1. **pytest fast**(unit + integration + release + docs) — 任何 cell 失败即 fail-fast。
2. **pytest network** — 仅在 `ubuntu-latest + Python 3.12` 单 cell 跑,避免 8× 模型下载。

### 4.3 pre-commit hook(可选,不在本方案硬要求)

提供 `scripts/pre-commit-quick.sh` 跑 `pytest -m "unit and not network"`,但**不强制安装**;由开发者在 `.git/hooks/pre-commit` 自行 symlink。

## 5. Coverage 测量

### 5.1 配置

- `pyproject.toml` 加 `[tool.coverage.run]` / `[tool.coverage.report]`,source = `src/mneme`。
- `[dev]` extra 加 `coverage>=7.5,<8`。
- 不设 `fail_under`(观察期,见 §2)。

### 5.2 运行命令

- `make test-cov` → `coverage run -m pytest -m "not network" && coverage report -m`
- CI 在 `pytest fast` 后跑 `coverage xml` 上传 artifact(不上 Codecov,保持零依赖)。

### 5.3 基线记录

首次跑 `make test-cov` 后,把各模块覆盖率记入 `docs/superpowers/reports/2026-07-12-mneme-test-coverage-baseline.md`,作为后续 PR 的对比锚点。预期 L1 (okflib) > 90%,L2 (indexlib) > 70%(受 sqlite-vec 边界限制)。

## 6. Fixture 策略

现有 fixture 散落在 `tests/fixtures/` 下 5 个子目录(e2e_ingest / e2e_lint / e2e_query / blackbox_news) + `sample-bundle/`。本方案**不重构 fixture 目录**,只做两件事:

1. **`tests/fixtures/README.md`**(新增):每个子目录一行说明 + 创建/修改规则(命名约定、是否可改)。
2. **`tests/conftest.py` 补注释**:解释 `sys.path.insert` 为什么必要(src layout),避免后人误删。

`test_retrieval_bench.py` 依赖的 `/Users/scott1743/Desktop/佳都/飞书文档库` 路径保留 skip 逻辑,不迁入仓库(141 个 .md 不属于 mneme 工程层)。

## 7. 已知陷阱文档化

### 7.1 subprocess + monkeypatch 失效

`test_e2e_ingest.py::test_step_six_reindex_then_step_seven_search_finds_each_concept` 在进程内 monkeypatch `indexlib.default_embed_fn`,但通过 subprocess 调 `mneme reindex`,subprocess 不继承 monkeypatch,实际触发真实 fastembed 模型下载。

**处理**:在本方案中**不修逻辑**,只在 `test_e2e_ingest.py` 顶部 docstring 加一段注释说明此限制,并把该测试函数显式打 `network` marker。逻辑修复留给后续单独 PR(可考虑加 `--embedder` CLI flag 或改用 in-process reindex)。

### 7.2 test_blackbox_news.py 的 embedder 选择

`NewsKeywordEmbedder` 是 count-based,与真实 BGE 嵌入语义不同。它在 10 个领域查询上能命中 top-3,但**不能**作为检索质量证据——那是 `test_retrieval_bench.py` 的职责。`test_blackbox_news.py` 只验证"写入 → 索引 → 搜索 → 命中"的布线,不验证语义质量。

**处理**:在该文件 docstring 已有说明,本方案不重复。

## 8. 交付物清单

| # | 文件 | 类型 | 描述 |
|---|---|---|---|
| 1 | `pyproject.toml` | 修改 | 注册 6 个 marker;`addopts = "-m 'not network'"`;加 coverage 配置;dev extra 加 coverage |
| 2 | 18 个测试文件 | 修改 | 在每个文件顶部加 `pytestmark = pytest.mark.<layer>`;个别函数叠加 `@pytest.mark.network` |
| 3 | `Makefile` | 新增 | `test-fast` / `test` / `test-full` / `test-cov` / `test-news` 五个 target |
| 4 | `tests/fixtures/README.md` | 新增 | 每个子目录一行说明 + 修改规则 |
| 5 | `tests/conftest.py` | 修改 | 加注释说明 sys.path.insert 必要性 |
| 6 | `.github/workflows/ci.yml` | 修改 | pytest 步骤拆 fast + network 两步;加 coverage xml 上传 |
| 7 | `TESTING.md`(仓库根) | 新增 | 对外可读的测试指南:如何跑、marker 含义、CI 矩阵说明 |
| 8 | `docs/superpowers/reports/2026-07-12-mneme-test-coverage-baseline.md` | 新增 | 首次 coverage 基线报告 |

**不动**:`src/mneme/**`、`skills/mneme/**`、现有测试逻辑。

## 9. 执行步骤

1. **pyproject.toml**:注册 marker + addopts + coverage 配置 + dev dep 加 coverage。
2. **18 个测试文件**:加 `pytestmark`,个别函数打 `@pytest.mark.network`。
3. **Makefile**:写 5 个 target。
4. **tests/fixtures/README.md**:列每个子目录。
5. **tests/conftest.py**:加注释。
6. **.github/workflows/ci.yml**:拆 fast + network 步骤,加 coverage。
7. **TESTING.md**:写对外指南。
8. **本地验证**:`make test-fast` → `make test-cov` → `pytest -m ""` 全跑通。
9. **基线报告**:跑 `make test-cov`,把 `coverage report -m` 输出整理成 markdown 表格存入 reports/。
10. **一次 commit**:`test(strategy): layer markers + coverage baseline + TESTING.md`。

## 10. 验证标准

- [ ] `pytest` 默认跑跳过 network,~10s 内完成,全绿。
- [ ] `pytest -m "unit"` < 2s。
- [ ] `pytest -m ""` 全跑通(需网络),~90s。
- [ ] `make test-cov` 产出 `coverage.xml` + 终端报告。
- [ ] CI 矩阵的 fast 步骤在 8 cell 都 < 30s;network 步骤只在单 cell 跑。
- [ ] `TESTING.md` 让新贡献者 5 分钟内知道怎么跑测试。
- [ ] 基线报告记录 okflib / indexlib / cli / config / indexlib 等模块的覆盖率。

## 11. 非目标

- **不重构测试逻辑**:任何"这个测试写法不对"另开 issue。
- **不引入新测试框架**(unittest / hypothesis / pytest-xdist):保持 stdlib + pytest。
- **不设 coverage 硬阈值**:观察期先建基线。
- **不迁入 141 文档语料**:它属于 dogfood 数据,不属于工程层。
- **不加 pre-commit 强制**:提供脚本但不安装。

## 12. 风险与回退

| 风险 | 影响 | 缓解 |
|---|---|---|
| `addopts = "-m 'not network'"` 让旧用户 `pytest` 行为变 | 默认跳过 network 测试 | 在 TESTING.md 与 CHANGELOG 显式说明;`pytest -m ""` 可跑全部 |
| marker 误标导致分层运行结果不一致 | 某些测试被错误跳过 | 验证步骤 §10 的 `pytest -m ""` 全跑通作 sanity |
| coverage 配置拖慢 CI | CI 时间增加 | coverage 只在 fast 步骤跑,network 步骤不跑 |

回退:所有改动可在一次 revert commit 中撤销,不影响 1.0.0 release gate 已闭合的状态。

---

*本方案遵循 AGENTS.md 的工程过程约定,所有产物在 `docs/superpowers/plans/` 下。执行阶段不修改 `src/mneme/` 与 `skills/mneme/`,不触发新的 release gate 闭合。*
