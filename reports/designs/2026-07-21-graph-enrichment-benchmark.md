# Graph Enrichment Retrieval Benchmark

> **状态**：冻结设计 · 2026-07-21
> **目的**：测量 agent-extracted Graph 对页面召回和 hybrid 检索的增量价值。

## 1. 研究问题

本实验不再使用历史 5 题 qrels，也不把单人手选题当作主结论。它回答三个更窄、可复现的问题：

1. 在同一份 Markdown bundle 上，enriched Graph 是否比 deterministic Graph 增加实体/关系查询的 Recall@10？
2. 在 Graph 变稀疏或实体不匹配时，hybrid 是否保持 FTS5 的词法召回？
3. 增益是否集中在 Graph-native query family，而不是泛化为所有检索任务？
4. 加入同领域事件文档后，原始相关目标能否继续留在 top-10，还是被新语料挤出？

## 2. 系统与对照

| 阶段 | Graph | FTS5 | 含义 |
|---|---|---|---|
| `L1` | 无 | 全局 | 词法基线 |
| `G0` | pages/tags/links | 无 | deterministic Graph |
| `G1` | G0 + frozen extraction manifest | 无 | enriched Graph |
| `H0` | G0 | 全局 | deterministic hybrid |
| `H1` | G1 | 全局 | enriched hybrid |

同一 bundle、同一 qrels、同一 top-k（10）用于所有阶段。`G1/H1` 的 enrichment 输入是冻结的 `.exp-full/wiki/.mneme/graph-extractions.json`；该输入只用于生成派生索引，不改变 Markdown。

每个阶段同时运行两个配对 corpus condition：

- `base`：原始 142 页私有 Feishu Markdown bundle；
- `expanded`：在 base 上增加 `reports/events.zip` 中 77 篇互不重复的 AI 事件页，共 219 页。

事件页只接受 pages/tags/links 的 deterministic Graph 构建，不追加事后 enrichment。原始 qrels 在扩增前冻结，事件页没有经过穷尽相关性标注，因此 expanded 指标只解释为“原始目标保留率/排序”，不能把事件命中直接判为错误，也不能当作完整 relevance 质量。

## 3. Query families

冻结 80 条 qrels，分成四类：

- `entity_exact`（24）：抽取实体名作为 query，相关页面是 manifest 中通过 `mentions` 支持该实体的页面。
- `entity_context`（24）：从实体描述生成不含实体名的上下文 query，测试 Graph/FTS 对实体语境的召回。
- `relation`（24）：由 subject + predicate + object 组成，相关页面是支持该关系的 source pages。
- `no_answer`（8）：随机固定的 `__mneme_no_answer_XX__` 字符串，测 false-positive rate。

前 3 类是 **construction-aware diagnostic benchmark**：qrels 来自冻结 extraction manifest，因此适合回答 Graph enrichment 的机制问题，不声称代表独立人工标注的通用搜索质量。`no_answer` 不依赖 extraction 内容。

实体和关系选择规则在 `run_graph_enrichment_benchmark.py` 中固定：去除路径/URL/数字噪声，要求有效 UTF-8、最小置信度 0.80，并用 SHA-256 稳定排序后取样。冻结后的 qrels 单独保存，运行时不重新生成。

## 4. 指标与统计

主指标以“agent 在最多读取 10 个候选时能否拿到所需页面”为目标：

- **Macro Recall@10**：逐题计算标注目标召回率后取平均，是主质量指标；
- **Query Success@10**：至少召回一个标注目标的问题比例；
- **Recovered targets**：召回目标数 / 80 个冻结目标，保留可核查的微观计数；
- **First-hit pages**：首个标注目标的排名；完全 miss 记为 11，表示候选预算耗尽，越低越好；
- **Expansion retention**：expanded/base Macro Recall@10，同时报告绝对差和保留比例；
- warm query P50/P95 latency；
- Graph entity/relation/component/orphan counters。

普通分类 Accuracy 不纳入，因为 query-document 负例没有被穷尽标注，且大量 true negative 会制造虚高分数。固定分母 Precision@10 与 F1@10 不纳入 headline，因为 65/72 道题只有一个标注目标，Precision@10 的理论上限仅 0.111。nDCG/MRR 继续保留在机器可读逐题结果中供排序审计，但不是本实验的主要结论。

每个 query 作为 bootstrap 重采样单位，报告 Macro Recall、Query Success、First-hit pages 和配对 Recall 差的 95% percentile confidence interval（10,000 次、固定 seed）。报告 query family small multiples，不把不同 family 混成一个未经解释的总分。延迟使用同一进程 warm cache，索引构建单独报告。

飞书重复导出形成的 `foo.md` / `foo--2.md` 若正文完全相同，评测时视为一个文档等价类：qrels 只保留 canonical path，候选列表也在截取 top-10 前去重。否则重复文件会虚增相关文档分母并占用排名位置。

## 5. 失效与解释规则

- `G1 > G0` 的 Recall 增益只说明 enrichment 对 Graph-native 查询有帮助，不证明通用语义检索优于 L2。
- `H1 < L1` 是实现回归，必须单独标红，不能用 Graph health 解释带过。
- `H1 < G1` 说明融合权重或分数校准有问题，报告必须保留该事实。
- 任何 qrel 由 extraction 自动产生的结果，都标注 construction-aware，不与独立人工 qrels 混合。
- expanded corpus 中新增事件页属于 unjudged topical additions；报告必须使用 target-retention 表述，不得称其为独立相关性评测。

## 6. 产物

- `graph-enrichment-benchmark.qrels.jsonl`：冻结 query/qrels/category；
- `graph-enrichment-benchmark.results.jsonl`：逐 corpus、逐 query、逐 stage 结果；
- `graph-enrichment-benchmark.manifest.json`：base/expanded corpus、event archive、manifest hash、代码 revision、参数、Graph health、统计量；
- `graph-enrichment-benchmark.html`：自包含科研报告，包含置信区间图、按 family 对比图、rank heatmap、延迟图和数据审计表。
