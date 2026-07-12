# Testing mneme

> 一份给新贡献者的 5 分钟测试指南。完整的测试方案设计见
> [`docs/superpowers/plans/2026-07-12-mneme-test-strategy.md`](docs/superpowers/plans/2026-07-12-mneme-test-strategy.md)。

## 快速开始

```bash
# 1. 安装开发依赖(含 pytest + coverage)
pip install -e '.[dev,validate,index,toml10]'

# 2. 跑测试(默认跳过需要网络的测试)
make test           # 或: pytest

# 3. 想看覆盖率?
make test-cov
```

**预期结果**:126 passed, 15 deselected,~15 秒。

## 三档运行命令

| 命令 | 跑什么 | 耗时 | 用途 |
|---|---|---|---|
| `make test-fast` | 只跑 `unit` 层 | <2s | 改一个函数后秒级反馈 |
| `make test` | 跑除 `network` 外的全部 | ~15s | 本地提交前 |
| `make test-full` | 跑全部含 `network` | 60-90s | release 前完整验证 |
| `make test-cov` | `make test` + coverage 报告 | ~20s | 看 src/mneme 覆盖率 |
| `make test-news` | 只跑黑盒新闻测试 | ~1s | 快速验证 init/ingest/search/lint 布线 |

## 6 个 marker

每个测试文件顶部有 `pytestmark = pytest.mark.<LAYER>`,个别函数叠加 `@pytest.mark.network`。

| marker | 含义 | 离线? | 典型耗时 |
|---|---|---|---|
| `unit` | 单函数/单模块纯逻辑,无外部 IO | ✅ | <1s |
| `integration` | 跨模块组合,仍进程内 | ✅ | 1-3s |
| `e2e` | 通过 CLI subprocess 跑完整 bundle 流程 | ⚠️ 部分 | 5-30s |
| `release` | 发布门禁:wheel/入口/版本/预算/漂移 | ✅ | 3-10s |
| `docs` | 文档冻结规则 | ✅ | <1s |
| `network` | 需要 HuggingFace 模型下载 | ❌ | 30-90s |

`pytest` 不带参数时,`pyproject.toml` 的 `addopts = "-m 'not network'"` 默认跳过 network 测试。要跑全部用 `pytest -m ""`。

## 测试文件分层

| 文件 | 主 marker | 函数数 | 备注 |
|---|---|---|---|
| `test_okflib.py` | `unit` | 39 | OKF v0.1 合规库,纯 stdlib |
| `test_tools_helpers.py` | `unit` | 3 | bundle 路径解析 + slug |
| `test_config.py` | `unit` | 9 | TOML 配置往返读写 |
| `test_cli.py` | `unit` | 9 | CLI 参数 + 退出码,monkeypatch |
| `test_indexlib.py` | `unit` | 13 | L2 索引原语,sqlite-vec |
| `test_integration.py` | `integration` | 1 | init → reindex → search 全链 |
| `test_e2e_ingest.py` | `e2e` | 6 | ingest 7 步流水线 |
| `test_e2e_lint.py` | `e2e` | 5 | lint 全规则矩阵 |
| `test_e2e_query.py` | `e2e` | 7 | search 布线 + 降级 |
| `test_retrieval_bench.py` | `e2e` + `network` | 3 (×5 参数化) | 真实 141 文档语料 |
| `test_blackbox_news.py` | `e2e` | 7 | 10 篇新闻端到端黑盒 |
| `test_install.py` | `release` | 10 | wheel 构建 + 新 venv 安装 |
| `test_entrypoint.py` | `release` | 4 | console script 可工作 |
| `test_version.py` | `release` | 2 | pyproject == __version__ |
| `test_release_budget.py` | `release` | 5 | 资源预算 + 依赖上界 |
| `test_skill_drift.py` | `release` | 3 | SKILL EN/ZH 漂移 |
| `test_skill_text.py` | `docs` | 3 | SKILL 文本冻结规则 |
| `test_docs.py` | `docs` | 2 | AGENTS/CLAUDE 一致性 |

## Fixture

测试夹具在 [`tests/fixtures/`](tests/fixtures/) 下,每个子目录的用途见 `tests/fixtures/README.md`。

## CI

`.github/workflows/ci.yml` 有三个 job:

1. **test**(8 cell 矩阵:Python 3.10–3.13 × ubuntu/macos)— 跑 fast 测试 + coverage xml,每个 cell 上传 artifact。
2. **network**(单 cell:Python 3.12 ubuntu)— 只跑 `network` marker 测试,允许 skip 不允许 fail。
3. **wheel-smoke**(单 cell)— 在新 venv 装 wheel 跑 `mneme init` + `mneme lint`。

## 已知陷阱

### subprocess + monkeypatch 失效

`test_e2e_ingest.py::test_step_six_reindex_then_step_seven_search_finds_each_concept` 在进程内 monkeypatch `indexlib.default_embed_fn`,但通过 subprocess 调 `mneme reindex` 时 subprocess 不继承 monkeypatch,实际触发真实 fastembed 模型下载。该测试已显式打 `@pytest.mark.network`,默认跳过。逻辑修复留给后续 PR。

### NewsKeywordEmbedder 不是检索质量证据

`test_blackbox_news.py` 用 count-based embedder,只验证"写入 → 索引 → 搜索 → 命中"的布线,不验证语义检索质量。后者由 `test_retrieval_bench.py` 在真实 141 文档语料上验证(Recall@5 = 1.000, MRR = 0.800)。

### test_retrieval_bench.py 依赖外部语料

`/Users/scott1743/Desktop/佳都/飞书文档库/` 是用户私有数据,不进仓库。测试在找不到时 `pytest.skip`,不 fail。

## 新增测试时

1. 在文件顶部加 `pytestmark = pytest.mark.<LAYER>`(参考 §6 marker 表)。
2. 如果测试需要网络,加 `@pytest.mark.network`。
3. 如果用新 fixture,在 `tests/fixtures/` 下建子目录并更新 `tests/fixtures/README.md`。
4. 跑 `make test` 确认默认跑能过。
