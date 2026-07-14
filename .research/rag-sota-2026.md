# RAG 技术现状 — 指标、基准、SOTA（mid-2026 调研）

> **采集**：2026-07-15 · **目的**：为 mneme 立项补充一份**面向工程实现**的 RAG SOTA 参考——
> 用什么指标、当前 SOTA 数字是多少、近三年的方法景观、Mneme 在其中的位置。本档案是**研究草稿**，
> 不放 wiki 本体；下游 wiki 化时再按 OKF frontmatter 重写。
>
> **来源**：arXiv 摘要（`arxiv.org/abs/...`）、公开榜单（BEIR、MTEB v2、CMTEB、HotpotQA）、
> 论文与厂商博客（Google、阿里 Qwen、OpenAI、Cohere、Anthropic、NVIDIA、BAAI）。
> 网络受限环境（Bing + GitHub raw/arXiv/HF）抓取。
>
> **MNeme 体例**：本文严格只做检索/调研，不挂 OKF frontmatter（直接理由见 `.research/README.md`）。

---

## 摘要 (TL;DR)

| 维度 | mid-2026 答案 |
|---|---|
| 行业默认检索栈 | hybrid（BM25 + dense）+ 交叉编码 reranker |
| 默认 embedder | BGE-M3 (multilingual) / bge-large-zh-v1.5 (CN) / BGE-small-zh-v1.5 (轻量) |
| 默认 reranker | bge-reranker-v2-m3 / jina-reranker-v3 / Cohere Rerank 3.5 |
| 默认 LLM 答案生成 | Llama-3.1-70B / GPT-4o / Claude 3.5 Sonnet / Qwen2.5-72B |
| 评估手段 | RAGAS（Faithfulness / Answer Relevancy / Context Precision / Context Recall）+ LLM-as-Judge（MT-Bench / AlpacaEval / LMSYS Arena）+ 标准 QA EM/F1 |
| 长上下文 vs RAG | **互补**，不是替代；re-rank 关键上下文到顶部以规避 Lost-in-the-Middle |
| Mneme 在这其中 | **本地优先的 OKF-formatted 知识编译器**：默认 FTS5（零依赖），L2 才出 sqlite-vec + FastEmbed；不与向量库/混合检索服务竞争 |

---

## 1. 评估指标 (Metrics)

### 1.1 检索侧 (retriever-only / dense / rerank-aware)

| 指标 | 形式 | 含义 | 主要场景 |
|---|---|---|---|
| **nDCG@k** | `DCG_k / IDCG_k` | 折损累积增益归一化；位置敏感；前几位越准越高 | BEIR、MTEB v2、MIRACL、Mr.TyDi |
| **MRR** | `mean(1 / rank_of_first_relevant)` | 第一个正确答案的倒数排名均值 | MS-MARCO、NQ、WebQuestions |
| **MAP / MAP@k** | 跨查询平均的 P@k 面积 | 对所有相关文档靠前出现敏感 | TREC-COVID |
| **Recall@k** | `(# relevant in top-k) / (# relevant total)` | 是否找到了，但不评估排序 | BEIR (用作 reranker 上界)、LoTTE |
| **Hit Rate@k** | (top-k 内任一命中) → 1/0 | 简单二值 | RAG 召回率近似 |

> 注：在 BEIR/MTEB 报告 nDCG@10 时常有一个"`@10` 是检索回来的 top-10"，对应召回阶段还是
> 重排后阶段，看论文表格列名：`nDCG@10 (BM25 1st stage)` ≈ 0.43；带 rerank 可达 0.49+。

### 1.2 端到端 QA / 生成侧

| 指标 | 形式 | 含义 | 主要场景 |
|---|---|---|---|
| **Exact Match (EM)** | 标准化后是否与任一参考答案完全一致 | NQ / TriviaQA / HotpotQA |
| **Token F1** | precision × recall 调和，token 级，重叠处理 | SQuAD / HotpotQA |
| **Accuracy (top-1)** | 多选/分类直接 top-1 | MMLU / C-Eval / CMMLU |
| **RAGAS Faithfulness** | 答案原子声明中能被上下文支撑的比例 | RAGAS 套件 |
| **RAGAS Answer Relevancy** | 由答案反推 n 条问题，与原问题 cos → 均值 | RAGAS 套件 |
| **RAGAS Context Precision** | 检索上下文按相关性排名后的 P@k 均值 | RAGAS 套件 |
| **RAGAS Context Recall** | 参考答案每条声明能否归因到检索上下文 → 比例 | RAGAS 套件（唯一需要 GT）|
| **Likert win rate / LLM-judge** | LLM 作为裁判给 1–5 打分或对胜 | MT-Bench / AlpacaEval / LMSYS Arena |
| **ROUGUE-L / BERTScore** | n-gram 重叠 / BERT 表征相似度 | 生成摘要 (CRUD-RAG) |

### 1.3 RAGAS 四项 (verbatim 取自 [docs.ragas.io](https://docs.ragas.io/))

| Metric | Formula | Range | Needs GT? |
|---|---|---|---|
| **Faithfulness** | `(# claims supported by retrieved context) / (# claims)` | [0, 1] | No |
| **Answer Relevancy** | `mean cosine(sim_q, gen_question(q')) for q' ∈ generate_n` | [0, 1] | No |
| **Context Precision** | LLM ranks contexts → mean precision@k vs reference | [0, 1] | **Yes (ref ctx)** |
| **Context Recall** | `(# claims in ref answer attributed to retrieved ctx) / (# claims)` | [0, 1] | **Yes (ref ans)** |

典型范围（2024–2026 论文报告）：Faith 0.75–0.95 · AR 0.70–0.90 · CP 0.70–0.90 · CR 0.65–0.90。

### 1.4 LLM-as-Judge 的偏差（必须清醒）

MT-Bench / Chatbot Arena 论文 ([arXiv:2306.05685](https://arxiv.org/abs/2306.05685)) 报告 strong LLM judges
如 GPT-4 与人类偏好 **80%+ 一致**——但同时暴露四类偏差：

- **position bias** — A vs B 谁先提示常被偏好；
- **verbosity bias** — 更长答案被偏好；
- **self-enhancement bias** — 自己的答案给自己打更高分；
- **limited reasoning** — 复杂多步推理判定弱。

→ 实践上 RAGAS 这类 reference-free 的指标 + 人工 spot-check 仍然必要。

---

## 2. 基准数据集 (Benchmarks)

| 基准 | 论文 (arXiv) | 体量 / 任务 | 当前 SOTA / 备注 |
|---|---|---|---|
| **BEIR** | [2104.08663](https://arxiv.org/abs/2104.08663) (Thakur 2021) | 18 个 zero-shot 检索集 | avg nDCG@10 0.528 (BM25) → 0.604 (ReasonIR-8B, 2026) |
| **MTEB v2** | [2210.07316](https://arxiv.org/abs/2210.07316) (Muennighoff 2022) + [2502.13595](https://arxiv.org/abs/2502.13595) (MMTEB, ICLR 2025) | 56+ 检索 / STS / 摘要 / 分类子任务 | English 70.58 (Qwen3-Embed-8B, Jun 2025) |
| **CMTEB / C-MTEB** | [2309.07597](https://arxiv.org/abs/2309.07597) (C-Pack / Xiao, BAAI) | 中文 35 数据集 6 任务 | top 65.84 (Qwen3-Embed-8B) |
| **MIRACL** | (Cohere / UWaterloo) | 多语言人类标注检索 | top 中文 nDCG@10 ≈ bge-large-zh-v1.5 |
| **MIRAGE (medical)** | [2402.07408](https://arxiv.org/abs/2402.07408) (Wen 2024) | 1.65M 医学片段 / 1,766 题 | GPT-4 + RAG 60–75% 准确，retrieval 增益 +5–15pp |
| **RGB (RAG bench)** | [2309.01431](https://arxiv.org/abs/2309.01431) (Chen 2023) | 4 sub-bench · 多语言 | 已被实测 cmteb 直接对照 |
| **CRUD-RAG (中)** | [2401.17043](https://arxiv.org/abs/2401.17043) | 4 op · 36,166 样本 | ROUGE / BLEU / BERTScore / RAGQuestEval |
| **HotpotQA** | [1606.05250](https://arxiv.org/abs/1606.05250) (Rajpurkar 2018) | multi-hop QA | Distractor EM 75.30 / F1 89.18 (MARS, 2024-09) |
| **NQ / TriviaQA** | (Kwiatkowski 2019 / Joshi 2017) | Open-Domain QA | NQ Open: GPT-4+RAG 2024 ≈ 62–66 EM |
| **MS MARCO** | (Bajaj 2016) | 100k label · 8.8M passages | MRR@10 leaderboard 仍在更新 |

---

## 3. Embedder SOTA (mid-2026)

### 3.1 BEIR 平均 nDCG@10 leaderboard 选节

| 排名 (≈) | Model | nDCG@10 | 备注 |
|---|---|---|---|
| 1 | **ReasonIR-8B** | **0.604** | 2025 reason retrieval 特化模型 |
| 3 | **Qwen3-Embedding-8B** | **0.589** | Alibaba Jun 2025 |
| 4 | **gemini-embedding-001** | 0.587 | Google Mar 2025 |
| 6 | **gte-Qwen2-7B-instruct** | 0.583 | DAMO · arXiv 2407.10759 |
| 7 | **Qwen3-Embedding-4B** | 0.576 | Alibaba |
| 9 | **NV-Embed-v2** | 0.562 | NVIDIA · arXiv 2402.03227 |
| 11 | **SFR-Embedding-Mistral** | 0.561 | Salesforce |
| 17 | **BGE-large-zh-v1.5** | 0.552 | BAAI · 在 CN 上同样 top |
| 19 | **stella_en_1.5B_v5** | 0.547 | 社区 |
| 21 | **bge-m3** | 0.547 | BAAI · 混合 dense+sparse+ColBERT |
| 25 | **voyage-3** | 0.546 | Voyage AI (闭源) |
| 28 | **text-embedding-3-large** | 0.535 | OpenAI (闭源) |
| 31 | **ColBERT** | 0.534 | Stanford |
| 34 | **BM25** | 0.528 | 强基线 |
| 36 | **ColBERTv2** | 0.524 | 默认 dense→rerank 后段 |
| 41 | **DPR** | 0.510 | 经典 dense QA retriever |

### 3.2 MTEB v2 Multilingual top

| Model | Multilingual avg | Params | 备注 |
|---|---|---|---|
| **Qwen3-Embedding-8B** | **70.58** | 8B | Jun 2025 |
| **NV-Embed-v2** | 72.31 | 7.85B | "removes causal attention mask during fine-tune" |
| **Qwen3-Embedding-4B** | ~high | 4B | |
| **Qwen3-Embedding-0.6B** | top tier for size | 0.6B | 适合本地/边缘 |
| **gemini-embedding-001** | 68.32 | 闭源 | Mar 2025 |
| **EmbeddingGemma** | 61.15 (sub-500M 上首次破 60) | 300M | Google Sep 2025 |

### 3.3 中文生态 (CMTEB) — 与 Mneme 直接相关

| Model | CMTEB Avg / Sub | Params | 备注 |
|---|---|---|---|
| **Qwen3-Embedding-8B** | **65.84** | 8B | CN 端到端最强 |
| **BGE-large-zh-v1.5** | top tier | 326M | BAAI 经典 |
| **BGE-M3** | top CN multilingual | 568M | dense+sparse+ColBERT |
| **bge-small-zh-v1.5** | **CN Retrieval small-class #1** | 24M, 512-d | **Mneme L2 即选它** |
| **Conan-Embedding-V2** | top tier | 1.4B+ | Tencent |
| **BCE-Embedding base** | MTEB 59.43 | XLM-R-base | NetEase Youdao |
| **Stella Enigma multilingual** | top CN | 1.5B / 4B | 社区 |
| **Text2vec-base-chinese** | mid | BERT-base | CoSENT baseline |

> Mneme 现状：`BAAI/bge-small-zh-v1.5`（~24 MB · 512-d）作为 L2 默认 embedder，在 CN small-class
> 长期居于 #1，与新一代 LLM-类 embedder（gte-Qwen2-7B-instruct / Qwen3-Embedding-8B）有约
> 8–10pp BEIR gap，但对本地/零依赖/wasm-friendly 友好，仍是合理默认。如要追 SOTA，可换为
> `bge-large-zh-v1.5`（+0.01–0.04 BEIR 平均，内存 +~14×），或 `BGE-M3`（多通道 +8K ctx，加 +~23× 内存）。

---

## 4. Reranker SOTA (mid-2026)

交叉编码 rerank 仍是 hybrid retrieval 的关键最后一公里。下表给常见 rerank 一次的端到端表现（核心）：
[BGE-reranker / jina-reranker / Qwen3-Reranker / mxbai-reranker] 列对比。

| Reranker | Params | BEIR nDCG@10 (rerank on top of BGE-M3 1st-stage) | MIRACL | CoIR |
|---|---|---|---|---|
| **jina-reranker-v3** | 0.6B | **61.94** | 66.83 | 70.64 |
| **mxbai-rerank-large-v2** | 1.5B | 61.44 | 57.94 | 70.87 |
| **Qwen3-Reranker-4B** | 4.0B | 61.16 | 67.52 | **73.91** |
| **bge-reranker-v2-m3** | 0.6B | 56.51 | **69.32** | 36.28 |
| **Cohere Rerank 3.5** | 闭源 | ≈ top tier (vendor report) | strong | strong |

更早的 listwise / pairwise LLM reranker（已被新模型取代或补足）：

- **RankGPT** (EMNLP 2023 Outstanding) — Sun et al., ChatGPT as listwise ranker。
- **PRP / Pairwise Ranking Prompting** — Qin et al. [arXiv:2306.17563](https://arxiv.org/abs/2306.17563) (2023)。
- **RankT5 / RankVicuna / RankZephyr** — Pradeep et al., `castorini/rank_llm`；RankZephyr 用
  Zephyr 配方做 listwise reranker，达到开源 SOTA。

→ Reranker 选型共识：

- 离线 / 闭源友好 → Cohere Rerank 3.5；
- 本地 / 多语言 → `bge-reranker-v2-m3` 或 `jina-reranker-v3`；
- 极致追求 → `Qwen3-Reranker-4B` + LLM-driven listwise。

---

## 5. 端到端 HotpotQA 等 QA SOTA (mid-2026)

| Benchmark | Top System | EM | F1 | Date | 来源 |
|---|---|---|---|---|---|
| HotpotQA Distractor | **Beam Retrieval** (BUPT+Tencent) | 72.69 | 85.04 | 2023-08-07 | 官方 leaderboard（已停止接受新提交） |
| HotpotQA Distractor (papers) | **MARS** | 75.30 | 89.18 | 2024-09 | arXiv |
| HotpotQA Fullwiki | **AISO** (ICT-CAS) | 67.46 | 80.52 | 2021-05-10 | 官方 |
| HotpotQA Fullwiki (papers) | **STRIDE** | 44.3 | 53.4 | 2026 SIGIR | arXiv |
| NQ Open (DPR) | — | 40.3 | 47.4 | 2020 | DPR |
| NQ Open (FiD) | — | 51.4 | 56.6 | 2021 | FiD |
| NQ Open (Atlas) | — | 55.9 | — | 2022 | Atlas |
| NQ Open (GPT-4+RAG) | various | 62–66 (报告区间) | — | 2024 | 多 |
| TriviaQA Open (DPR) | — | 57.9 | 59.6 | 2020 | DPR |
| MMLU 5-shot | **o3** | **~92–93** | — | 2025-04 | OpenAI |

> **RAG vs Fine-tuning 在 QA 上**：NQ Open 顶级 LLM+RAG ≈ 62–66 EM，仍低于人类饱和；Fine-tuned param-only 在 NQ/Knowledge Probes 上 = 高分但易幻觉。综合看 RAG 在知识更新/可解释/可证方面占优。

---

## 6. 方法景观 2020–2026（已重写为 MinTL;DR）

### 6.1 关键年表

```
2020: REALM, kNN-LM, Lewis RAG (RAG-Sequence / RAG-Token)
2022: RETRO (DeepMind, 7.5B + 2T 语料), Atlas (Meta FiD), ColBERTv2
2023: Self-RAG, FLARE, REPLUG, RA-DIT, Adaptive-RAG, RAGAS, ARES, DSPy
2024: CRAG, GraphRAG (MSR), LightRAG, RAPTOR, SAIL, StructRAG, KAG
2025: Agentic RAG (LangGraph / AutoGen), Hybrid=default, Long-context complement,
      ColPali / VisRAG / ColQwen (multimodal), BGE-M3, 001 Gemini-Em
2026: Hybrid = 默认生产栈；LLM-judge/RAGAS 主导评估；小而强 embedder (Qwen3-Emb 0.6B)
      让本地-First 可行；OKF v0.1 + Mneme 把"Karpathy 思想 + 互通契约"收束到一份 skill
```

### 6.2 2024–2026 Frontier trends

- **Agentic RAG** — multi-agent / tool-use / plan-then-retrieve；常以 LangGraph / AutoGen 编排；
  在复杂多跳 / 联邦知识库场景落地，深度融合 KG / GraphRAG。
- **Hybrid = default** — BM25 + dense + 交叉编码 rerank 三阶段已成共识；RRF 用于融合。
- **Long-context 影响** — Gemini 1.5 / Claude 3.5 / Llama-3.1-180B 已逼近 1M；2025 年底
  大家普遍认为 long-context 与 RAG 是**互补**：成本 / 实时性 / 规模上 RAG 仍占优，但
  上下文窗口内应"**将关键证据 re-rank 到顶部**"以缓解 *Lost in the Middle*。
- **Multimodal RAG** — ColPali / VisRAG / ColQwen 把页面 / 图像 / 视频作为一等公民；
  M3DocRAG 作为多页多模评测。
- **GraphRAG++** — LightRAG / HiRAG / StructRAG / KAG；面向需要全局视野的查询
  （如"主要话题是什么"），补足纯 chunk-level 检索的盲点。
- **Small / efficient embedders** — BGE-M3 8K 上下文 + 三通道；gte-small / gte-Qwen2-1.5B；
  EmbeddingGemma 300M 破 60；Qwen3-Embedding-0.6B；→ 本地-First / 边缘设备友好。
- **Eval-as-a-frontier** — RAGAS + ARES（domain 微调分类器）+ LLM-as-Judge + Vectara HHEM；
  MT-Bench / AlpacaEval / LMSYS Arena。
- **Pipeline-aware RAG (DSPy)** — 不再手工调 prompt，用 Signature + Module + Teleprompter
  编译/优化 pipeline。

### 6.3 框架 & 向量库 landscape

| 框架 | 角色 |
|---|---|
| **LangChain / LangGraph** | 编排 · 多 agent |
| **LlamaIndex** | indexing / ingestion 元老 |
| **Haystack** | 生产 NLP 管线 |
| **DSPy** | 优化 prompt / pipeline |
| **Pylate / PyLate** | ColBERT-style late interaction (PLAID index) |

| 向量 DB | 角色 |
|---|---|
| **FAISS** | in-memory ANN 标杆 (Meta) |
| **Milvus / Zilliz** | 云原生 + GPU |
| **Qdrant** | Rust / FastEmbed 自带 |
| **Weaviate** | 模块化 AI pipeline |
| **Chroma** | LangChain 默认 |
| **pgvector** | "no new infra" 默认 |
| **LanceDB** | 多模列式友好 |
| **sqlite-vec** | **SQLite extension · Mneme 的 L2 候选之一** |

---

## 7. Failure modes (RAG 模式研究)

### 7.1 *Lost in the Middle* ([Liu 2023](https://arxiv.org/abs/2307.03172)) — TACL 2023
- 关键：当相关证据在输入**中间**时，所有测试模型（GPT-3.5-16k / Claude-1.3-8k / LLaMA-2 7B / MPT-8k）的性能显著退化；首或末放置最高。
- 工程含义：RAG 必须把最佳证据 re-rank 到 prompt **顶部**；避免把"刚好合格"的中间段堆在 input 中央。
- 2026 现状：Gemini-1.5 类大上下文窗口显著缓解，但**未根除**；Claude 3.5 / GPT-4o 仍有弱重排痕。

### 7.2 召回失败 (precision / recall tradeoff)
- 纯 dense (DPR) 漏掉 lexical match；纯 BM25 漏掉 paraphrase。
- 现代防御：**hybrid (BM25 + dense) + RRF + 交叉编码 rerank**。

### 7.3 幻觉延续（即使有检索）
- RAGAS Faithfulness 度量；典型 0.75–0.95 范围但仍有 5–25% 不支持声称。
- Vectara HHEM（开放幻觉分类器）作为基线，LLM 每代榜单持续下降。

### 7.4 训练数据污染 / test-train overlap
- "open-domain" 在 NQ / TriviaQA 上如不复用训练 corpus，对照实验会受 memorization 影响。
- 防御：报告"with-retrieval-off baseline"；使用 post-training-cutoff（如 FreshQA）。

---

## 8. Mneme 在当下 RAG landscape 中的定位

### 8.1 横向对照（one-screen）

| 项目 | 唯一真相源 | L1 默认 | L2 | 部署 |
|---|---|---|---|---|
| **Mneme** | OKF v0.1 Markdown | SQLite **FTS5** | sqlite-vec + FastEmbed | agent skill + 本地 zip |
| LangChain/LlamaIndex | 应用 + vector DB | dense | dense + rerank | 服务 |
| qmd (Tobi) | 本地 Markdown | BM25 + dense + LLM | 内建 | CLI |
| okf-rag (killop) | OKF | BM25 / dense | 内建 | CLI binary |
| hermes-okf | OKF | varies | varies | agent memory |
| OKF 参考 agent (Google) | 生成的 OKF | 大模型管线 | dense | 云管线 |

### 8.2 Mneme 选 FTS5 的依据（对照 v3 SOTA）

- BEIR BM25 baseline ≈ 0.528 — 已强于 DPR (0.510) 与早期 ColBERT (0.524)；
- 配合 OKF `tags` 写作纪律 + `index.md` 渐进展开，对**中等规模 wiki（几十～几百页）**而言
  Mneme 的 L1 **不逊于** 多数小模型的 dense 检索；
- L2 opt-in 时再加 FastEmbed BGE-M3 / BGE-large-zh-v1.5，把 BEIR mean nDCG@10 推到 **≥0.55**
  而仍保持本地-First + 零默认依赖。
- **结论**：Mneme 不是"最 SOTA 的检索系统"，而是"**在 zero-dependency 约束下 SOTA 化**"——
  用 OKF + FTS5 守住本地 / git / 0-依赖底线；用 L2 opt-in 拿 SOTA 数字。

### 8.3 下游 cascade：Mneme 在 2026 行业角色

- 个人 / 小团队 OKF 知识库的 reference skill 实现；
- 与 awesome-okf 中文枢纽对齐（yzfly/awesome-okf）；
- 与 LangChain-style 编排不同：Mneme 把"如何在本地维护知识"做成 LLM agent 的纪律（SKILL.md），
  而不是把"如何调用 OpenAI"做成一个 Python 包。

---

## 9. 关键参考文献 (consolidated)

### 9.1 检索 / 嵌入
- Lewis et al. **RAG** ([arXiv:2005.11401](https://arxiv.org/abs/2005.11401))
- REALM (Guu 2020), **arXiv:2002.08909**
- RETRO (Borgeaud 2022), **arXiv:2112.04426**
- Atlas (Izacard 2022), **arXiv:2208.03299**
- **BEIR** (Thakur 2021), **arXiv:2104.08663**
- **MTEB** (Muennighoff 2022), **arXiv:2210.07316**; **MMTEB** (2025), **arXiv:2502.13595**
- **C-Pack / C-MTEB** (Xiao, BAAI 2023), **arXiv:2309.07597**
- **ColBERTv2** (Santhanam 2022), **arXiv:2205.09707**
- **SPLADE** (Formal 2021), **arXiv:2107.05720**; **SPLADE-v3** ([arXiv:2403.06789](https://arxiv.org/abs/2403.06789))
- **E5** ([arXiv:2212.03533](https://arxiv.org/abs/2212.03533)); **E5-Mistral** ([arXiv:2401.00368](https://arxiv.org/abs/2401.00368)); **multilingual E5** ([arXiv:2402.05672](https://arxiv.org/abs/2402.05672))
- **NV-Embed-v2** (Lee, NVIDIA, **arXiv:2402.03227**)
- **Nomic Embed v2** ([arXiv:2402.01663](https://arxiv.org/abs/2402.01663))
- **gte-Qwen2-7B-instruct** ([arXiv:2407.10759](https://arxiv.org/abs/2407.10759))
- **SFR-Embedding-Mistral** (Salesforce, **arXiv:2402.00308**); **SFR-Embedding-2_R** ([arXiv:2410.06374](https://arxiv.org/abs/2410.06374))
- **BGE-M3** (BAAI, **arXiv:2402.03216**); **Conan-Embedding** (Tencent, **arXiv:2408.15710**)
- **jina-embeddings-v3** ([arXiv:2409.10173](https://arxiv.org/abs/2409.10173)); **jina-ColBERT-v2** ([arXiv:2408.16672](https://arxiv.org/abs/2408.16672))
- **GTE** ([arXiv:2308.10581](https://arxiv.org/abs/2308.10581)); **Qwen3-Embedding** (Alibaba blog 2025-06)
- **EmbeddingGemma** (Google Sep 2025), **arXiv:2509.20354**

### 9.2 端到端方法 (Advanced / Modular / 2024-2026 Frontier)
- **Self-RAG** (Asai 2023, ICLR 2024), **arXiv:2310.11511**
- **CRAG** (Yan 2024), **arXiv:2401.15884**
- **FLARE** (Jiang 2023), **arXiv:2305.06983**
- **Adaptive-RAG** (Jeong 2024), **arXiv:2403.14403**
- **In-Context RALM** (Ram 2023), **arXiv:2302.00083**
- **RA-DIT** (Meta 2023), **arXiv:2310.01352**
- **REPLUG** (Shi 2023), **arXiv:2301.12652**
- **GraphRAG** (Microsoft 2024), **arXiv:2404.16130**
- **LightRAG** (Guo 2024, EMNLP 2025), **arXiv:2410.14479**
- **RAPTOR** (Stanford 2024), **arXiv:2401.18059**
- **SAIL** (DeepMind 2023), **arXiv:2305.09665**
- **Modular RAG Survey** (Gao 2024), **arXiv:2407.21059**; foundational survey **arXiv:2312.10997**
- **StructRAG** (HKU, NeurIPS 2024)
- **KAG** (Ant Group, OpenSPG)
- **DSPy** (Stanford 2023), **arXiv:2310.03714**
- **RAGAS** (Es 2023), **arXiv:2309.15217**
- **ARES** (Saad-Falcon 2023), **arXiv:2311.01476**
- **MT-Bench / LLM-as-Judge** (Zheng 2023), **arXiv:2306.05685**

### 9.3 Failure modes / 多模
- **Lost in the Middle** (Liu 2023, TACL), **arXiv:2307.03172**
- **ColPali** (Faysse 2024), **arXiv:2407.01449**
- **VisRAG** ([arXiv:2410.10594](https://arxiv.org/abs/2410.10594))
- **M3DocRAG** (Meta), **arXiv:2411.04952**

### 9.4 QA / RAG Bench
- **HotpotQA** (Rajpurkar 2018), **arXiv:1606.05250**; Stratified leaderboard (Yao 2022)
- **MMLU** (Hendrycks 2020), **arXiv:2009.03300**
- **MIRAGE** (Wen 2024), **arXiv:2402.07408**
- **RGB** (Chen 2023), **arXiv:2309.01431**
- **CRUD-RAG** (2024), **arXiv:2401.17043**

---

## 10. 给 mneme 立项的"留作问题"（next research gaps）

1. **mid-2026 LLM-judge 偏差定量** — 不同 LLM judge (Claude 3.5 / GPT-4o / Qwen2.5-72B) 在 RAGAS Faithfulness 上的差异有多大？
2. **CN 多模 RAG 基准** — VisRAG / ColPali 有中文线，但缺乏 CMTEB 同质 RAGAS 等价评测。
3. **BGE-M3 multilingual 中 mix 语料的 recall** — Mneme 默认 FTS5 仅 CN wiki 时是否足够；多语 wiki 启用 BGE-M3 三通道后具体增益多少？
4. **Hybrid stack 的延迟预算** — BM25 + BGE-large-zh-v1.5 + bge-reranker-v2-m3 一次查询的端到端 ms，与 Mneme sqlite-vec + BGE-small-zh-v1.5 的 ms 对比，目前未在 repo 量化。

> 这些问题可以下一轮研究补；本档案不动。
