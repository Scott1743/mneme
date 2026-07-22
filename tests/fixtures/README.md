# tests/fixtures/

测试夹具目录。每个子目录服务一个或多个测试文件,内含**固定的、版本化的**测试输入 —— 不要在测试运行时修改它们。

## 目录清单

| 目录 | 用途 | 使用者 | 可改? |
|---|---|---|---|
| `blackbox_news/` | 10 篇多领域新闻 `.md`,端到端黑盒测试输入 | `test_blackbox_news.py` | 加文件需同步改 `EXPECTED_CONCEPTS`;改内容需同步改 keyword 列表 |
| `e2e_ingest/` | 单源 ingest 流水线 fixture(1 个 `source.md`) | `test_e2e_ingest.py` | 改 `source.md` 内容会改 slug 派生,需同步测试断言 |
| `e2e_lint/` | `clean_bundle/`(0 error)+ `dirty_bundle/`(每条 OKF 规则触发一次，raw fixture 使用 `.md.raw`) | `test_e2e_lint.py` | 改 `dirty_bundle/` 结构需同步 `test_e2e_lint.py` 的断言矩阵 |
| `e2e_query/` | 5 个概念页 + index + log,query 布线测试 | `test_e2e_query.py` | 改概念页会改 search 期望,需同步断言 |
| `broken_link/` / `empty_type/` / `extra_keys/` / `log_bad_format/` / `log_out_of_order/` / `missing_frontmatter/` / `nested_index_with_fm/` / `root_index_extra/` / `root_index_no_okf_version/` / `type_as_list/` / `type_non_string/` / `type_whitespace/` / `unknown_type/` / `yaml_malformed/` | OKF 合规规则反例集 — 每个子目录触发一条 SPEC §4 / §9 规则 | `test_okflib.py` | 改任一反例需同步 `test_okflib.py` 的对应测试函数 |

## 修改规则

1. **新增 fixture 子目录**:在 `tests/fixtures/<name>/` 下建,并在本表加一行。
2. **修改现有 fixture**:确认所有引用该 fixture 的测试仍能通过 —— fixture 是契约,不是便利样本。
3. **不要在 fixture 里放临时实验代码**:它们会被 commit 进仓库并作为回归基线。
4. **不要放二进制文件**:OKF/Mneme 中图片不是一等公民(AGENTS.md §7)。

## 外部语料(不在仓库内)

`test_retrieval_bench.py` 依赖 `/Users/scott1743/Desktop/佳都/飞书文档库/` 的 141 个 `.md`。该路径是用户私有数据,不进仓库;测试在找不到时 `pytest.skip`。
