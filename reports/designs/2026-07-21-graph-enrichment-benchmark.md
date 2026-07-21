# Graph Enrichment Retrieval Benchmark

> **状态**：冻结设计 · 2026-07-21
> **目的**：测量 agent-extracted Graph 对页面召回和 hybrid 检索的增量价值。

## 1. 研究问题

本实验不再使用历史 5 题 qrels，也不把单人手选题当作主结论。它回答三个更窄、可复现的问题：

1. 在同一份 Markdown bundle 上，enriched Graph 是否比 deterministic Graph 增加实体/关系查询的 Recall@10？
2. 在 Graph 变稀疏或实体不匹配时，hybrid 是否保持 FTS5 的词法召回？
3. 增益是否集中在 Graph-native query family，而不是泛化为所有检索任务？

## 2. 系统与对照

| 阶段 | Graph | FTS5 | 含义 |
|---|---|---|---|
| `L1` | 无 | 全局 | 词法基线 |
| `G0` | pages/tags/links | 无 | deterministic Graph |
| `G1` | G0 + frozen extraction manifest | 无 | enriched Graph |
| `H0` | G0 | 全局 | deterministic hybrid |
| `H1` | G1 | 全局 | enriched hybrid |

同一 bundle、同一 qrels、同一 top-k（10）用于所有阶段。`G1/H1` 的 enrichment 输入是冻结的 `.exp-full/wiki/.mneme/graph-extractions.json`；该输入只用于生成派生索引，不改变 Markdown。

## 3. Query families

冻结 80 条 qrels，分成四类：

- `entity_exact`（24）：抽取实体名作为 query，相关页面是 manifest 中通过 `mentions` 支持该实体的页面。
- `entity_context`（24）：从实体描述生成不含实体名的上下文 query，测试 Graph/FTS 对实体语境的召回。
- `relation`（24）：由 subject + predicate + object 组成，相关页面是支持该关系的 source pages。
- `no_answer`（8）：随机固定的 `__mneme_no_answer_XX__` 字符串，测 false-positive rate。

前 3 类是 **construction-aware diagnostic benchmark**：qrels 来自冻结 extraction manifest，因此适合回答 Graph enrichment 的机制问题，不声称代表独立人工标注的通用搜索质量。`no_answer` 不依赖 extraction 内容。

实体和关系选择规则在 `run_graph_enrichment_benchmark.py` 中固定：去除路径/URL/数字噪声，要求有效 UTF-8、最小置信度 0.80，并用 SHA-256 稳定排序后取样。冻结后的 qrels 单独保存，运行时不重新生成。

## 4. 指标与统计

主指标：

- nDCG@10（binary relevance，支持多相关页面）；
- Top-1 accuracy、Precision@10、macro Recall@10、macro F1@10；
- Hit@10、MRR@10；
- `no_answer` false-positive rate；
- warm query P50/P95 latency；
- Graph entity/relation/component/orphan counters。

每个 query 作为 bootstrap 重采样单位，报告 95% percentile confidence interval（10,000 次、固定 seed）。报告 query family small multiples，不把不同 family 混成一个未经解释的总分。延迟使用同一进程 warm cache，索引构建单独报告。

`Top-1 accuracy` 定义为第一名是否相关；它不是逐文档分类 accuracy。`Precision@10` 使用固定分母 10，未填满的位置按未命中处理。F1 在每个 query 上由 Precision@10 与 Recall@10 计算，再做 macro average。

飞书重复导出形成的 `foo.md` / `foo--2.md` 若正文完全相同，评测时视为一个文档等价类：qrels 只保留 canonical path，候选列表也在截取 top-10 前去重。否则重复文件会虚增相关文档分母并占用排名位置。

## 5. 失效与解释规则

- `G1 > G0` 只说明 enrichment 对 Graph-native 查询有帮助，不证明通用语义检索优于 L2。
- `H1 < L1` 是实现回归，必须单独标红，不能用 Graph health 解释带过。
- `H1 < G1` 说明融合权重或分数校准有问题，报告必须保留该事实。
- 任何 qrel 由 extraction 自动产生的结果，都标注 construction-aware，不与独立人工 qrels 混合。

## 6. 产物

- `graph-enrichment-benchmark.qrels.jsonl`：冻结 query/qrels/category；
- `graph-enrichment-benchmark.results.jsonl`：逐 query、逐 stage 结果；
- `graph-enrichment-benchmark.manifest.json`：corpus/manifest hash、代码 revision、参数、Graph health、统计量；
- `graph-enrichment-benchmark.html`：自包含科研报告，包含置信区间图、按 family 对比图、rank heatmap、延迟图和数据审计表。
