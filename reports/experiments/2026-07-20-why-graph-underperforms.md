# 为什么 G(graph-only)在 5 题历史回归上效果差

> **日期**:2026-07-20 · **基于**:v4.0.1 修复 description 列后的实验数据
> **数据来源**:`reports/experiments/2026-07-20-cross-version-historical.{manifest.json,results.jsonl}`

---

## TL;DR

G 阶段在 5 题上 nDCG@10=0.486,远低于 L2 的 0.826。**这不是 Graph 算法本身的失败,而是 bootstrap bundle 的 Graph 派生基础太薄弱**:

1. **Graph 的关系几乎全是 `tagged_by`**(426/428),且所有页面共享同 3 个 tag(dogfood/source/feishu),Graph 在结构上退化为"142 个页面通过 3 个 tag hub 连成一大块"。
2. **`relates_to` 只有 2 条**(beta → alpha,即 `_bundle` fixture 里的 `Alpha uses Beta`),在真实 bootstrap bundle 里**没有任何跨页 Markdown link**。
3. **G 的召回 = seed 命中 + BFS 2 跳**,seed 命中取决于 description/name/properties 是否含查询词;BFS 2 跳在 "142 页全连在 3 个 tag hub 上" 的拓扑里,**2 跳能触达几乎所有页面**,但 `graph_score = 1/(1+distance)` 无法区分"直接命中"和"通过共享 tag 间接关联"的页面。

结果是:G 在 query 直接命中 description 的页面上表现好(H01/H02 rank=1),在 description 不含查询词的页面上失败(H04/H05)。

---

## 详细分析

### 1. Graph 拓扑结构:tag hub 退化

```
relations 类型分布:
  relates_to: 2      ← 仅 2 条跨页 link
  tagged_by: 426     ← 142 页 × 3 tag(dogfood/source/feishu)

tag entities:
  'dogfood': 142 pages
  'source':  142 pages
  'feishu':  142 pages
```

**含义**:bootstrap 脚本给每个 Source 概念页写入相同的 `tags: [dogfood, source, feishu]`。Graph 派生的 `tagged_by` 关系把 142 个页面全部连到同 3 个 tag 实体上。Graph 拓扑是**一个以 3 个 tag 为 hub 的星形结构**,没有有意义的跨页关系。

**影响**:
- `bfs_neighborhood(depth=2)` 从任何 seed 出发,2 跳能触达几乎所有页面(seed → tag hub → 其他页)。
- `graph_score = 1/(1+distance)` 中,直接命中页 distance=0 → score=1.0;通过 tag 关联的页 distance=1 或 2 → score=0.5 或 0.33。
- 但由于 **所有页面都有相同的 tag**,BFS 触达的"page 候选集"几乎总是全部 142 页,`graph_score` 无法有效区分。

### 2. 每题失败/成功的根因

| Query | 结果 | 根因 |
|---|---|---|
| **H01 gstack** | rank=1 ✅ | expected page description 是 `<title>gstack 调研报告 — Hermes 上的 sprint 工作流魔法</title>`,直接含 "gstack"。seed 命中 description,BFS distance=0,score=1.0,rank=1。 |
| **H02 Claude Code 工作流** | rank=1 ✅ | expected page description 含 "Claude Code"。同 H01,直接命中。 |
| **H03 银行回单** | rank=4 ⚠️ | description 含 "银行回单" 的有 4 页:<br>1. ARxXdsmbao…(录音主题:银行回单与流水匹配)<br>2. NqhBdw36XoINh2xvOzxcfZBvnFf--2.md(智能纪要:银行回单)<br>3. NqhBdw36XoINh2xvOzxcfZBvnFf.md(智能纪要:银行回单)<br>4. UCvpdz5z8oZqXTxCpD2cLAObnse.md(**expected**,银行回单与流水匹配交付方案)<br>expected 页 description 是 `<title>银行回单与流水匹配交付方案</title>`,也含 "银行回单",seed 命中。但 `find_entity_by_name` 的 `LIMIT 50` 按 `name` 字典序排序,expected 页排在第 4。BFS 后 graph_score 都是 1.0(distance=0),FTS5 在 G+L1 里能把它排到前 3,但 G 阶段没有 FTS5,按 SQL 返回顺序取 top-k,expected 掉到 rank=4。 |
| **H04 录音** | 未召回 ❌ | expected page `Sic7dPX3aoxVByxxWqqcZAQunRb.md` description 是 `<title>AI存储市场调研报告(2026年6月)</title>`,**不含 "录音"**。Graph 里 description 含 "录音" 的有 18 个 entity(都是"录音主题:..."的会议纪要),expected 页不在其中。BFS 触达的 2 个节点是 "录音主题" 系列页,expected 页 distance=None。**失败原因:expected 页的 description 是从正文首行提取的,而正文首行是标题,不含 "录音" 关键词**。FTS5 能命中是因为正文里有 "录音";L2 能命中是因为 embedding 捕捉到语义关联。 |
| **H05 Hermes** | 未召回 ❌ | expected page `XVFudUEQeoXQjixSS9zckeNonAg.md` description 是 `<title>Agent Skill:赐予 AI 的操作手册</title>`,**不含 "Hermes"**。Graph 里只有 1 个 entity description 含 "Hermes"(gstack 调研报告页)。expected 页的正文里有 Hermes(line 79),但 description 没有。**失败原因:同 H04,description 不含查询词,Graph 无法命中**。 |

### 3. 为什么 L1(FTS5)和 L2(embedding)在 H04/H05 上能召回?

- **L1(FTS5)**:FTS5 索引 `title + description + tags + body`。H04 的 expected 页正文里有 "录音"(AI 存储市场调研报告里提到录音存储方案),FTS5 能命中。H05 的 expected 页正文里有 "Hermes"(line 79),FTS5 能命中。
- **L2(embedding)**:BGE 模型把 "录音" 和 "AI 存储市场调研报告" 映射到相近的向量空间(录音 → 存储),把 "Hermes" 和 "Agent Skill" 映射到相近空间(Hermes 是希腊神使,与 "赐予 AI 的操作手册" 有语义关联)。embedding 能捕捉字面无关但语义相关的匹配。

### 4. Graph 的核心缺陷:description 只是正文的"首行"

bootstrap 脚本的 description 提取逻辑(`scripts/bootstrap_dogfood.py`):

```python
description = f"<title>{title}</title>"  # 或从正文首行提取
```

description 是**正文首行或标题**,不是全文摘要。当查询词出现在正文其他位置但不在标题时,Graph 无法命中。

**这不是 Graph 算法的问题,而是 Graph 派生数据的质量问题**。Graph 只有 `name`(路径)、`description`(首行)、`properties`(title/type)、`tags`(3 个共享 tag)、`links`(2 条)可用,信息量远低于 FTS5 的全文索引或 L2 的语义向量。

---

## 5. 为什么 G+L1(hybrid)比 G 好?

G+L1 的融合逻辑(`indexlib.py:700-756`):

```python
final_score = (α * graph_score + β * fts_score) / (α + β)
```

- G 阶段提供 graph_score(结构化召回),FTS5 提供 fts_score(全文词法召回)。
- 对于 H04/H05,G 阶段 graph_score=0(未命中),但 FTS5 在 graph 候选集里能找到正文含查询词的页面,fts_score > 0,所以 final_score > 0。
- 对于 H01/H02,G 阶段 graph_score=1.0(直接命中),FTS5 也能命中,final_score = (0.4×1.0 + 0.4×0.x)/0.8 ≈ 0.5+0.2x,比纯 G 的 1.0 低,但 rank 仍靠前。

**G+L1 的 nDCG@10=0.600 比 G 的 0.486 高 0.114**,提升来自 H04/H05 上 FTS5 补充了 Graph 漏掉的页面。

---

## 6. 改进方向

### 6.1 短期(v4.0.x):不修改 Graph 算法,只改进 description 提取

bootstrap 脚本的 description 不应只是"正文首行",应提取**前 N 个有意义的句子**或**关键词/实体列表**。例如:

```python
# 从正文提取前 3 句或前 200 字符作为 description
description = extract_first_sentences(body, max_chars=200)
```

这能让 Graph 的 description 匹配覆盖更多查询词。

### 6.2 中期(v4.1,Graph Phase 2):agent 辅助的实体/关系深度提取

- **实体提取**:从正文提取人名、产品名、技术名作为 entity,不依赖 description。
- **关系提取**:从正文提取 "A 使用 B"、"A 基于 B"、"A 与 B 相关" 等关系,补充 `relates_to`。
- **tag 细化**:不用共享的 dogfood/source/feishu,而是从正文提取主题 tag(如 "银行回单"、"Hermes"、"录音")。

这需要 agent 介入,是 v4-design.md §10 Phase 2 的内容。

### 6.3 长期(v4.2+,Graph Phase 3):entity embedding + 社区检测

- **entity embedding**:用 BGE 给每个 entity 的 description 生成向量,Graph 搜索时用向量相似度 + BFS 混合召回。
- **社区检测**:用 Leiden 算法把 Graph 划分成主题社区,搜索时优先召回与 query 同社区的页面。

这需要 embedding 依赖,与 L2 的依赖管理一致。

---

## 7. 结论

G 阶段在 5 题历史回归上 nDCG@10=0.486,**不是 Graph 算法失败,而是 bootstrap bundle 的 Graph 派生基础太薄弱**:

1. Graph 拓扑退化为 tag hub 星形结构(426 tagged_by vs 2 relates_to)。
2. description 只是正文首行,查询词出现在正文其他位置时 Graph 无法命中。
3. `graph_score = 1/(1+distance)` 在 tag hub 拓扑里无法有效区分页面。

**Graph 的价值需要在 "tags 有区分度、links 有跨页关系、description 有语义信息" 的 bundle 上才能体现**。bootstrap bundle 是测试夹具,不是真实 wiki;真实 wiki 应该有 agent 维护的 tags 和 links。80 题主分析应在更接近真实 wiki 的 bundle 上跑,或在 bootstrap 后补充 agent 提取的 tags/links。

**G+L1 的 hybrid 设计是正确的**:G 提供结构化召回(当 Graph 数据好时),FTS5 提供全文兜底(当 Graph 数据差时)。v4.0.1 修复 description 列后,G+L1 的 nDCG@10 从 0.400 提升到 0.600,证明 hybrid 路径是有效的。
