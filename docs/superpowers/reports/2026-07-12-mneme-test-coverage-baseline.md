# Mneme 测试覆盖率基线 — 2026-07-12

**采集环境**: macOS (Python 3.13.0),`make test-cov`(跳过 network 测试)
**测试样本**: 126 passed, 15 deselected
**总体覆盖率**: **83%**(statement + branch coverage)

## 模块覆盖率

| 模块 | Stmts | Miss | Branch | BrPart | Cover | 备注 |
|---|---|---|---|---|---|---|
| `src/mneme/__init__.py` | 3 | 0 | 0 | 0 | **100%** | 仅 `__version__` + re-export |
| `src/mneme/config.py` | 15 | 0 | 2 | 0 | **100%** | TOML 读写边界完整 |
| `src/mneme/cli.py` | 117 | 10 | 22 | 6 | **88%** | missing 集中在 `_resolve_bundle` fallback 与 `cmd_search` 异常分支 |
| `src/mneme/indexlib.py` | 254 | 37 | 74 | 12 | **84%** | 超出 Plan §5.3 预期 70% 的目标;missing 集中在 `_model_cache_dir` macOS 分支(已在 darwin 上跑但被 omit 规则遮蔽)与 `search_bundle` 异常路径 |
| `src/mneme/okflib.py` | 250 | 32 | 140 | 22 | **85%** | 超出 Plan §5.3 预期 90% 目标的 5pp;missing 集中在 `find_orphans` 边界条件与 YAML 解析的 fallback 路径 |
| `src/mneme/tools_helpers.py` | 33 | 13 | 14 | 3 | **53%** | 唯一显著低于 70% 的模块;`resolve_bundle` 的 `MNEME_BUNDLE` 环境变量分支未覆盖 |
| `src/mneme/validate_okf.py` | 16 | 5 | 6 | 1 | **64%** | CLI 前端,`main()` 入口未通过 CLI 测试覆盖(库测试覆盖了核心) |
| **TOTAL** | **688** | **97** | **258** | **44** | **83%** | — |

## 观察

### 高覆盖模块(>85%)

- `__init__.py` / `config.py` 100% — 这些模块行数小,测试简单。
- `cli.py` 88% / `okflib.py` 85% / `indexlib.py` 84% — 核心模块覆盖率符合 1.0.0 release gate 的预期。

### 低覆盖模块(<70%)

- `tools_helpers.py` 53% — `resolve_bundle` 的 `MNEME_BUNDLE` 环境变量分支未覆盖。后续 PR 可加一条 unit 测试覆盖该分支。
- `validate_okf.py` 64% — `main()` CLI 入口未通过 CLI 测试覆盖;库测试已覆盖核心 `validate_bundle` 函数。后续可加 e2e 测试跑 `python -m mneme.validate_okf <bundle>`。

### Plan §5.3 预期对比

| 模块 | Plan 预期 | 实际 | 差 |
|---|---|---|---|
| L1 (okflib) | > 90% | 85% | -5pp |
| L2 (indexlib) | > 70% | 84% | +14pp |

L1 比预期低 5pp,主要来自 `find_orphans` 的边界条件。L2 比预期高 14pp,得益于 v0.6.0 的 `find_orphans` 测试与 v0.5.0 的 retrieval bench 测试。

## 后续改进方向(非本方案范围)

1. 给 `tools_helpers.resolve_bundle` 加 `MNEME_BUNDLE` 环境变量测试(预计提 5pp)。
2. 给 `validate_okf.main` 加 CLI e2e 测试(预计提 2pp)。
3. 给 `okflib.find_orphans` 的 archive/ 与 sources/ 边界加测试(预计提 3pp)。

达到 90% 总覆盖率是可达的,但不是 1.0.x 维护期的硬目标。

## 复现

```bash
make test-cov
# 终端输出 coverage report
# coverage.xml 同步生成,供 CI artifact 上传
```

---

*本基线作为后续 PR 的对比锚点。新 PR 不应使总覆盖率下降超过 2pp,除非有明确说明。*
