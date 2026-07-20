# Mneme v0.5 / v2.0 / v3.0 / v4.0 跨版本检索对比实验设计

> **状态**：实验前设计（preregistered protocol）· 2026-07-20
> **前置产物**：
> - `reports/designs/3.2-retrieval-comparison.html`（0.5/2.2/3.2 三版本设计，本设计是其扩展）
> - `reports/experiments/2026-07-15-design01-historical.*`（5 题历史回归 L1/L2/L1+L2 结果）
> - `reports/experiments/2026-07-15-l1-pilot.*`（5 题 L1 FTS5-only pilot）
> - `docs/v4-design.md`（v4.0 Graph + hybrid 设计）
> **作者**：Scott1743 + 小刘鸭
> **预注册原则**：标注、runner、分析脚本必须在运行前冻结；历史 5 题保留为回归组，但不主导结论。

---

## 0. 实验定位

本设计把 3.2-retrieval-comparison.html 中的"0.5 / 2.2 / 3.2"扩展到 **0.5 / 2.0 / 3.0 / 4.0 四个发布版本**，并新增 v4.0 的 Graph + hybrid 路径。它不是 3.2 设计的替代，而是其超集：保留 L1/L2/L1+L2 三个阶段，新增 **G（graph-only）** 和 **G+L1（hybrid）** 两个阶段。

它**不替代** 80 题预注册主分析。5 题历史回归仍然是"可复现的回归组"，不得外推为主结论。80 题主分析仍是独立门槛。

---

## 1. 研究问题

**主问题**：在冻结的中文 Markdown 知识库上，v0.5 / v2.0 / v3.0 / v4.0 四个版本的检索路径，在召回、排序、延迟、可解释性、构建成本上各自提供多少净收益？

**不预设**"Graph 一定优于 FTS5"或"L2 一定优于 L1"。每个阶段的增益都要单独归因。

**子问题**（对应"跨版本对比实验需要回答的核心问题"）：

| # | 子问题 | 对比 | 主要指标 |
|---|---|---|---|
| Q1 | v4.0 Graph 在多跳/跨页关系问题上是否优于 v2.0 FTS5？ | G vs L1 | Recall@10, nDCG@10 |
| Q2 | v3.0 L2 在改写表达上是否优于 v2.0 FTS5？ | L2 vs L1 | Recall@10, nDCG@10 |
| Q3 | v4.0 hybrid (Graph+FTS5) 是否有累积收益，还是只是互补漏召回的补丁？ | G+L1 vs G, G+L1 vs L1 | nDCG@10, Hit Rate@10 |
| Q4 | L1+L2 RRF（v3.x 实验脚本）vs G+L1 加权（v4.0 CLI），哪种融合更适合中文知识库？ | L1+L2 vs G+L1 | nDCG@10, Recall@10 |
| Q5 | Graph 派生质量是否受限于 tags/links 的写作纪律？ | G+L1 在不同 tags 覆盖率 bundle 上 | nDCG@10, graph 健康指标相关性 |
| Q6 | v0.5 原始分数（Recall@5=1.000 / MRR=0.800）与 v3.3 复跑分数（L2 MRR@10=0.767）的差异从何而来？ | v0.5 原始 vs v3.3 复跑 | MRR@10, 排名分布 |
| Q7 | 5 题历史回归的结论能否外推到 80 题主分析？ | 5 题 vs 80 题 | 效应量稳定性 |

---

## 2. 系统矩阵

### 2.1 版本与检索路径

| 版本 | 发布日期 | 默认检索路径 | 本次运行 ID | 描述 |
|---|---|---|---|---|
| **v0.5.0** | 2026-07-12 | L2 语义（sqlite-vec + BGE） | `V0` | 历史语义基线；锁定依赖复跑 |
| **v2.0.0** | 2026-07-14 | L1 FTS5（title+description+tags+body） | `L1` | 零依赖词法基线 |
| **v3.0.0** | 2026-07-14 | L1 默认 + L2 显式 opt-in | `L2` | 纯语义检索（隔离 embedding 净效果） |
| **v4.0.0** | 2026-07-20 | L1 默认 + Graph + Hybrid | `G`, `G+L1` | Graph-only 与 Graph+FTS5 加权融合 |

### 2.2 运行阶段

| 运行 ID | 检索阶段 | 版本 | 目的 | 是否主比较 |
|---|---|---|---|---|
| `V0` | 0.5 dense 历史复跑 | v0.5 | 复现历史语义基线，标记可复现状态 | 是（标记） |
| `L1` | 2.0 FTS5 / BM25 | v2.0 | 零依赖 lexical 基线 | 是 |
| `L2` | 3.0 纯语义检索 | v3.0 | 隔离 embedding 净效果 | 是 |
| `L1+L2` | FTS5 + L2 + RRF | v3.0 | 检验词法+语义融合（实验脚本，非 CLI） | 是 |
| `G` | 4.0 Graph-only | v4.0 | 隔离 Graph BFS 的结构化召回 | 是 |
| `G+L1` | 4.0 Graph + FTS5 加权 | v4.0 | v4.0 CLI 默认 hybrid | 是（v4.0 主候选） |
| `L1+L2+rerank` | 混合 + cross-encoder | - | 未实现，不报告数值 | 否 |

### 2.3 融合公式对照

| 阶段 | 融合方式 | 参数 | 实现位置 |
|---|---|---|---|
| `L1+L2` | RRF: `score = Σ 1/(k+rank)` | k=60 | `reports/experiments/run_design01_historical.py:121` |
| `G+L1` | 加权: `final = (α·graph_score + β·fts_score)/(α+β)` | α=0.4, β=0.4, γ=0.2（未激活） | `skills/mneme/scripts/mneme/indexlib.py:644-756` |

**注意**：`G+L1` 的 `fts_score` 是 `1/(1+rank)` 的 RRF 式归一化，**不是 BM25 分数归一化**。这是 v4.0 实现的简化，与 `docs/v4-design.md §5.1` 声明的"BM25 rank 归一化"不一致。实验报告中必须标记此偏差。

---

## 3. 可比性证据链

沿用 3.2 设计的 A-B-C-D-E 五步链，但每一步都要明确四个版本如何共用。

### A · corpus（语料冻结）

- **同一份** Feishu Markdown 导出（142 文件，2,085,799 字符，aggregate SHA-256 `6bd159fd...`）。
- **同一份** bootstrap 概念页表示：`scripts/bootstrap_dogfood.py` 对四个版本共用，每个 raw source 生成一个 `type: Source` 概念页。
- **不重新蒸馏**：不得为了某个版本（如 v4.0 Graph）额外添加 tags 或 links。tags 一律是 bootstrap 写入的 `[dogfood, source, feishu]`。

### B · representation（表示冻结）

- 四个版本读取**同一份** bundle 目录（独立 tmp_path 副本，避免索引互相污染）。
- 排除规则一致：`.mneme/`、`sources/`、`external-sources/`、`index.md`、`log.md`。
- v4.0 的 Graph 从 bootstrap 写入的 tags + Markdown links 派生；不得手工补充 relations。

### C · qrels（标注冻结）

沿用 3.2 设计的 6 组 query：

| query 组 | 最低数量 | 目的 | 对应子问题 |
|---|---|---|---|
| 历史回归 | 5 | 复核 0.5 报告已知 query | Q6, Q7 |
| 精确词项 | 20 | 检验 FTS5 优势边界 | Q2（L2 是否退化） |
| 短语与改写 | 20 | 检验 dense/hybrid 对非字面表达 | Q2 |
| 跨表达/多跳 | 15 | 检验多概念与跨页证据 | **Q1（Graph 核心价值）** |
| 长上下文排序 | 10 | 检验 rerank 是否值得 | （rerank 未实现，仅留坑） |
| 无答案 | 10 | 检验 false-positive rate | 全部 |

- 目标 ≥80 题，分级相关性：`2=直接回答, 1=有用支持, 0=不相关`。
- **独立双人标注**，先报告 weighted Cohen's κ，再记录分歧与裁决。
- **标注先于运行**；不得让检索结果反向塑造答案。

### D · runners（runner 冻结）

- 每个阶段输出同构 JSONL：`query_id, query, expected_path, rank, candidate_paths, stage_scores, score_kind, elapsed_ms, mneme_version, config_sha256`。
- 固定 seed=20260715，离线模型 revision（`BAAI/bge-small-zh-v1.5`），RRF k=60，Graph depth=2，α/β/γ 使用 v4.0 CLI 默认值。
- 每个阶段的 `mneme_version` 必须与该版本的实际 `__version__` 一致；v0.5 复跑需 checkout 到 v0.5 commit。

### E · analysis（分析冻结）

- 同一脚本计算所有指标：Recall@{1,3,5,10}、Hit Rate@10、MRR@10、MAP@10、nDCG@10。
- bootstrap 95% CI（query 为重采样单位，10000 次）。
- paired randomization test（同 query 配对），Holm 校正三组比较（L2-L1, G-L1, G+L1-L1）。
- 索引构建重复 5 次，warm/cold 查询各 30 次。
- LLM judge 若启用：随机 A/B、隐藏系统身份、统一回答长度、不同 judge 模型、每组人工抽查 ≥20 条。

---

## 4. v4.0 特有的实验约束

v4.0 的 Graph 是 disposable accelerator，以下约束必须在 runner 中显式实现：

### 4.1 Graph 重建的健康度记录

每次 `reindex --graph` 后，runner 必须调用 `graphlib.graph_health` 并记录：
- `entity_count`, `relation_count`, `orphan_entity_count`, `unresolved_page_count`, `connected_component_count`
- 这些数字进入 manifest，用于 Q5（Graph 派生质量 vs tags 覆盖率）。

### 4.2 Graph 候选不足时的处理

`search_hybrid` 在 graph 有部分候选但 FTS5 在候选页中无命中时，返回 `fts_score=0` 的 graph-only 候选（见评审 H3）。runner 必须记录这种情况，标记 `fallback_used: false, partial_graph_candidates: true`，不得静默丢弃。

### 4.3 L2 + Graph 共存场景

v4.0 CLI 在 L2 已激活时默认走 L2，不走 hybrid。runner 必须显式区分：
- `G+L1` 运行时 `active_retrieval_mode` 必须是 `fts5`（确保 `search` 默认走 hybrid）。
- `L2` 运行时 `active_retrieval_mode` 必须是 `l2`。
- 两者使用不同的 tmp_path bundle 副本。

### 4.4 v0.5 复跑的代码 checkout

v0.5 的 `reindex_bundle` / `search_bundle` API 与 v3.3 不完全兼容。runner 必须在 v0.5 commit 上跑，记录 commit hash；不得用 v3.3 API 复跑 v0.5。

---

## 5. 预注册指标

沿用 3.2 设计，新增 Graph 特有指标：

### 5.1 主指标
- **nDCG@10**（处理分级相关性）

### 5.2 召回与排序
- Recall@{1,3,5,10}, Hit Rate@10, MRR@10, MAP@10

### 5.3 拒答
- 无答案 query 的 false-positive rate（top-10 中是否有任何 grade≥1 的结果）

### 5.4 Graph 特有（Q1, Q5）
- **Graph reachability**：graph 命中的实体数 / query 中可识别实体数
- **Graph coverage**：graph 候选页面数 / FTS5 全局候选页面数
- **Graph health correlation**：nDCG@10 与 `{entity_count, connected_component_count, orphan_ratio}` 的 Spearman 相关

### 5.5 工程
- 索引时长（5 次重复，中位 + P95）
- 索引字节数（fts.db / l2.db / graph.db 分别报告）
- 冷启动（首次查询）+ warm P50/P95
- 峰值 RSS
- 模型下载时间（仅 L2/G+L1 含 embedding 时；不得混入 steady-state）

---

## 6. 统计规则

沿用 3.2 设计，新增四版本校正：

- query 为重采样单位，bootstrap 95% CI（10000 次）。
- paired randomization test，主比较三组：`L2-L1`, `G-L1`, `G+L1-L1`。
- Holm 校正三组（α=0.05）。
- 报告效应量 ΔnDCG@10 与 CI，不以 `p<0.05` 单独作结论。
- 5 题历史回归的 p 值仅作审计记录，不得作为主结论。
- **80 题主分析** 必须在标注完成后才能运行；5 题历史回归可先跑，作为 runner 正确性验证。

---

## 7. 图表与报告

### 7.1 必须产出的图表

| 图表 | 回答的问题 | 格式 |
|---|---|---|
| 阶段瀑布图 | L1→L2→L1+L2→G→G+L1 的 nDCG@10 增量与 95% CI | 嵌入 HTML |
| 任务类型热图 | 按 query 组（精确/改写/多跳/无答案）比较 6 阶段 | 嵌入 HTML |
| 质量-成本前沿 | 横轴 P95 延迟，纵轴 nDCG@10，点面积=索引大小 | 嵌入 HTML |
| Graph 健康度仪表盘 | entity/relation/component/orphan 计数 | 嵌入 HTML |
| 证据排序审计 | 多跳题中正确证据的 rank 分布 | 表格 |

### 7.2 产物清单

- `reports/experiments/2026-07-20-cross-version.manifest.json`：corpus hash、qrels 版本、4 个 commit、依赖锁定、Graph 健康度。
- `reports/experiments/2026-07-20-cross-version.results.jsonl`：每阶段每 query 的 rank/path/score/耗时。
- `reports/experiments/2026-07-20-cross-version.html`：自包含报告。
- 明确标记"5 题历史回归"与"80 题主分析"；两者不可混用。

---

## 8. 发布门禁

v4.0 不需要在每一类 query 上击败 v2.0/v3.0。发布报告必须证明：

1. **G+L1 在"跨表达/多跳"集合上**相对 L1 有正向效应量及 95% CI（Q1）；若不显著，报告应明确"Graph Phase 1 在多跳问题上未带来可证明收益"。
2. **L2 在"短语与改写"集合上**相对 L1 不退化（Q2）；若退化，说明 L2 在该语料上不值得 opt-in。
3. **G+L1 的延迟代价**（Graph BFS + FTS5 重排）必须在可接受范围内（P95 < 2x L1）；否则应考虑 Graph 增量更新优化。
4. **Graph 派生质量**（Q5）若与 tags 覆盖率强相关，应在报告中声明"Graph 在 tags 稀疏的 bundle 上不推荐"。

---

## 9. 实施步骤

### Phase A：5 题历史回归（runner 正确性验证）

**目标**：验证四版本 runner 在同一语料、同一 5 题上能跑通，产出可比较的 JSONL。

1. 扩展 `reports/experiments/run_design01_historical.py` → `run_cross_version.py`：
   - 新增 `G` 阶段：`graphlib.search_graph(graph_db, query, k=10)`
   - 新增 `G+L1` 阶段：`indexlib.search_hybrid(bundle, query, k=10)`
   - 保留 `L1`, `L2`, `L1+L2` 三阶段
   - v0.5 复跑：在 v0.5 commit 上 checkout 单独 runner，或用 v3.3 API 标记"v0.5 模拟"
2. 在 v4.0 commit 上运行 5 题，产出 `2026-07-20-cross-version-historical.{manifest.json,results.jsonl,html}`。
3. 与 `2026-07-15-design01-historical` 对比 L1/L2/L1+L2 三阶段，验证数字一致（除随机扰动）。

### Phase B：80 题主分析

**前置条件**：80 题独立双人标注完成，weighted Cohen's κ ≥ 0.6。

1. 冻结 qrels 到 `reports/experiments/2026-07-20-cross-version.qrels.jsonl`。
2. 在 v4.0 commit 上运行 6 阶段（V0 标记可复现状态，其余 5 阶段实跑）。
3. 产出 `2026-07-20-cross-version.{manifest.json,results.jsonl,html}`。
4. 按子问题 Q1-Q7 分别计算指标、CI、p 值，填入报告。

### Phase C：Graph 健康度分析（Q5）

1. 在不同 tags 覆盖率的 bundle 上跑 `G+L1`：
   - 原始 bundle（tags=[dogfood, source, feishu]，覆盖率 100%）
   - 去除 50% tags 的 bundle
   - 去除 100% tags 的 bundle（Graph 退化为纯 links 派生）
2. 计算每个 bundle 的 Graph 健康度 + nDCG@10，报告相关性。

---

## 10. 已知风险与缓解

| 风险 | 缓解 |
|---|---|
| v0.5 代码与当前 Python 3.13 不兼容 | 在 v0.5 commit 上用 Python 3.11 venv 单独跑 |
| 5 题样本太小，p 值无意义 | 历史回归仅作 runner 验证，不作为主结论 |
| Graph 在 bootstrap bundle 上退化为孤立实体（tags 相同，links 稀疏） | Phase C 显式测量，报告中声明 |
| L2 模型下载在受限网络失败 | 提前 `pip install fastembed` 并缓存到 `~/Library/Caches/mneme/models/` |
| v4.0 `G+L1` 的 `fts_score` 是 RRF 式而非 BM25 归一化 | manifest 中记录此偏差，报告中单独讨论 |
| 80 题标注无法在实验窗口内完成 | Phase A（5 题）先跑，Phase B 延期不阻塞 v4.0 发布 |

---

## 11. 与 3.2 设计的差异

| 维度 | 3.2 设计 | 本设计 |
|---|---|---|
| 版本 | 0.5 / 2.2 / 3.2 | 0.5 / 2.0 / 3.0 / 4.0 |
| 阶段 | L1, L2, L1+L2, L1+L2+rerank | L1, L2, L1+L2, **G, G+L1**, (rerank 未实现) |
| 融合 | RRF only | RRF (L1+L2) + 加权 (G+L1) |
| Graph | 无 | 新增 Graph 健康度、Graph reachability、Q5 相关性分析 |
| qrels | 80 题 | 80 题（相同）+ 5 题历史回归（相同） |
| 发布门禁 | L1+L2 在"短语改写+跨表达"上正向 | G+L1 在"跨表达/多跳"上正向（Q1） |

---

## 附录 A：v4.0 Graph 实现评审摘要（2026-07-20）

本设计基于对 v4.0 实现的深度评审，评审发现的关键问题已在实验设计中显式约束：

- **C1（已修复）**：`cmd_dream` 无 `--bundle` 时崩溃。已修复并补回归测试。
- **H1（已修复）**：`_iter_page_records` 不捕获 `UnicodeDecodeError`，违反 OKF §9。已修复并补回归测试。
- **H2（已补测）**：`search_hybrid` 融合主路径零测试覆盖。已补 `test_hybrid_search_fuses_graph_recalled_pages_with_fts_rank`。
- **H3（未修复，已约束）**：`search_hybrid` 在 graph 有部分候选时不回退 FTS5。runner 必须记录 `partial_graph_candidates` 标记。
- **M1-M7（未修复）**：性能与测试缺口，不阻塞 Phase A，但 Phase B 前应补齐 M6（L2+Graph 共存测试）。

评审报告与修复 diff 见同日 commit。
