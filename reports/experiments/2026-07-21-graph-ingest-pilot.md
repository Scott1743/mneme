# Graph ingest 试点：agent 提取实体/关系对 G 与 G+L1 的影响

> **日期**：2026-07-21 · **基于**：v4.1.0（graph schema v2 + `mneme graph ingest`）
> **语料**：142 页飞书 dogfood bundle（`.exp-v41/wiki`，与 2026-07-20 跨版本回归同一 bootstrap）
> **结论边界**：这是**机制验证试点**，不是效果估计。只提取了 8/142 页，qrels 是 5 条历史手选题（其中 1 条本次证实为误标注）。不得外推为全量提取后的预期收益。

## 1. 背景与问题

v4.0.1 修复 description 列后，G 阶段仍有一个结构性盲区：**查询词只出现在正文、不出现在 frontmatter description 的页面，Graph 无法命中**（H05 "Hermes" 即此例）。Phase 2.1 落地了 `mneme graph ingest`：agent 读页面产出实体/关系 JSON，CLI 确定性入库，每个提取实体通过 `page -mentions-> entity` 边回连来源页。本试点验证该机制能否在真实语料上补上这个盲区。

## 2. 附带发现：H04 qrel 是误标注

试点前的事实核查发现，**H04「录音」的期望页 `Sic7dPX3aoxVByxxWqqcZAQunRb.md`（AI存储市场调研报告）正文中根本不含「录音」**（`录音|音频|语音|音视频` 均无匹配）。语料中真正含「录音」的是约 30 个妙记文档（`录音主题：` 头部）。

机制推断：2026-07-15 手工标注时，L2（BGE embedding）把「录音」与该页排到 rank 1（语义相近：录音 → 存储介质），标注者采信了这个语义假阳性。manifest 亦自注 `not independently double-annotated`。后果：

- L1（FTS5，词面匹配）在 H04 上 rank=null —— 这其实是**正确行为**，却被记为失败；
- L2 在 H04 上 rank=1 —— 这是**假阳性被当成真阳性**；
- 历史结论「L2 nDCG 0.826 显著优于 L1 0.400」有一部分是这个标注伪影。5 题样本下任何单题都占 20% 权重。

**处置**：为保持与 2026-07-15 / 2026-07-20 两轮数字可比，本试点不改历史 qrel，但后续 80 题主分析必须双人独立标注；并建议在下一轮回归中把 H04 期望页修正为真正的录音文档（如 `CuXIdbgAzoSAfUxEkXccEqe5nAe.md`「文字记录：新录音 2026年6月8日」）或标注为多相关页。

## 3. 设计

**样本**：8 页 = 4 个期望页（H01/H02 gstack 调研、H03 交付方案、H04 存储报告、H05 Skill 手册）+ 4 个竞争/相关页（H03 的两个银行回单妙记、H04 真正相关的「新录音」文字记录、含录音笔讨论的 CRM 妙记）。竞争页同样提取，避免「只富化相关页」的偏置。

**提取**：agent 逐页阅读后手工产出，忠实正文、不为查询塞词；8 页共 52 个 entity upsert、93 个 relation upsert（`mneme graph ingest` 零 warning）。跨页共享实体名（如「银行回单」「四要素匹配」「飞书知识库」在三页间复用），图因此连通。

**测量**：`reports/experiments/eval_graph_stages.py`，固定 bundle 原地对比 ingest 前后；G 参数与跨版本回归一致（k=10，depth=2，hybrid α=β=0.4）。

## 4. 结果

ingest 前基线与 2026-07-20 跨版本回归逐题一致（G: 1/1/4/—/—，G+L1: 1/1/1/—/—）。ingest 后 graph：193 entities（+47 llm）、519 relations（+91 llm）、1 个连通分量、0 orphan。

| Query | G 前 | G 后 | G+L1 前 | G+L1 后 |
|---|---|---|---|---|
| H01 gstack | 1 | 1 | 1 | 1 |
| H02 Claude Code 工作流 | 1 | 1 | 1 | **2 ↓** |
| H03 银行回单 | 4 | 4 | 1 | 1 |
| H04 录音（误标注） | — | —（正确） | — | — |
| H05 Hermes | — | **2 ✓** | — | **4 ✓** |
| **Recall@1** | 0.4 | 0.4 | 0.6 | 0.4 |
| **Recall@10** | 0.6 | **0.8** | 0.6 | **0.8** |
| **MRR@10** | 0.45 | 0.55 | 0.6 | 0.55 |
| **nDCG@10** | 0.486 | **0.612** | 0.600 | **0.612** |

（G 与 G+L1  ingest 后指标数值相同是巧合：两列 rank 集合 {1,1,4,—,2} 与 {1,2,1,—,4} 恰好同值置换。）

## 5. 逐题分析

- **H05（机制验证成功）**：提取的 `Hermes-Agent` 实体（来自 Skill 手册页正文第 88 行的图片说明）与 `Hermes` 实体（来自 gstack 页）被查询命中，期望页经 `mentions` 边 1 跳可达，G rank 2（仅次于本身 description 就含 Hermes 的 gstack 页）。**正文独有实体从此可达**——这正是 Phase 2 要补的盲区。
- **H03（不变）**：期望页本就可经 description 命中，ingest 后三个同主题妙记页仍排在它前面（四者都是真实相关页，排序属并列竞争）。
- **H04（不变，且正确）**：存储报告页诚实提取（AI存储/Agentic AI/HBM/KV缓存…）不含「录音」，故仍不可达——这是 qrel 错了，不是检索错了。G 的候选列表全部是真正含「录音」的妙记页。
- **H02（G+L1 副作用 1→2）**：查询分词出 token「工作流」，命中提取实体 `Skill Creator` 的 description（"让 Agent 自己造 Skill 的工作流"），Skill 手册页 1 跳可达，并在 hybrid 融合中反超期望页。该页（Agent Skill 手册）对「Claude Code 工作流」其实也算相关，但暴露了一个真实风险：**通用词 token 经 description 匹配会引入弱语义种子，改变 hybrid 排序**。

## 6. 结论

1. **机制成立**：agent 提取 → `graph ingest` 能让"正文才有、description 没有"的实体进入图谱并使来源页可达，G Recall@10 +0.2、nDCG@10 +0.126（8/142 页富化的下限演示）。
2. **种子质量是下一步的主战场**：弱 token（工作流/规划/方案这类通用词）经 description 列匹配会拉入噪声种子。候选改进（未实现）：种子按 name 精确/prefix/description 分级加权；graph_score 乘实体 confidence；通用词 stoplist 扩充。
3. **实体消歧缺失已可见**：`Hermes`（gstack host）与 `Hermes-Agent`（Skill 手册平台）是两个实体但语义重叠；Phase 2.3 的别名/消歧需要跟上。
4. **qrel 质量决定一切**：5 题手选组已发现 1 题误标注 + H02/H04 这类多相关页被标成单相关。80 题主分析的双人独立标注不可省。

## 7. 产物

- 提取 payload：`.exp-v41/extraction-pilot.json`（实验工作区，不入库）
- 评估脚本：[eval_graph_stages.py](eval_graph_stages.py)
- ingest 前基线：[2026-07-20-cross-version-historical.results.jsonl](2026-07-20-cross-version-historical.results.jsonl)
- 实现：`skills/mneme/scripts/mneme/graphlib.py`（`validate_extraction` / `ingest_extraction`）、`cli.py`（`graph ingest`）
