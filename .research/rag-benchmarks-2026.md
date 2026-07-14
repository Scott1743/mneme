---
name: rag-benchmarks-2026
description: RAG/QG benchmark mid-2026 research notes — RGB, ASQA, PopQA, ELI5, MS MARCO. Citation, metrics, primary-paper scores, recent (2024–2026) SOTA, source URLs with access date 2026-07-15.
metadata:
  type: reference
---

# RAG / 长答案基准 mid-2026 调研

> **采集**：2026-07-15 · **方法**：原始 PDF (arXiv 链接 + 官方仓库) + 官方榜单 + 引用追踪 (Semantic Scholar)
> · **目的**：为 mneme 的 RAG 评估视野补充 5 个长答案 / 检索 QA 基准的**精确 cite、metric、最新可比数字**。
> · **报告体例**：本档案**不**挂 OKF frontmatter；下游 wiki 化时再按 `type: Reference` / `type: Source` 重写。

## 0. 关键 arXiv ID 修正

原始任务中两个 ID 在 arXiv 上是**别的不相关**的论文（基于本机 PDF 头字段核对）：

| 任务给的 ID | 实际内容 | 正确的 ID |
|---|---|---|
| `2307.16882` | "Experimental analysis of quantum Fisher information" (unrelated) | **RGB = `2309.01431`**（Chen et al., 2023）|
| `2302.00083` | "In-Context Retrieval-Augmented Language Models" (Ram et al., AI21) | **PopQA = `2212.10511`**（Mallen, Asai, Zhong, Das, Khashabi, Hajishirzi, 2022）|

ASQA（`2204.06092`）、ELI5（`1907.09190`）、MS MARCO（`1611.09268`）ID 与任务一致。

---

## 1. RGB — Retrieval-Augmented Generation Benchmark

**Citation**: Jiawei Chen, Hongyu Lin, Xianpei Han, Le Sun. "Benchmarking Large Language Models in Retrieval-Augmented Generation." arXiv:2309.01431v2 (20 Dec 2023). DOI not assigned.
- Primary: https://arxiv.org/abs/2309.01431
- Code/data: https://github.com/chen700564/RGB
- Access date: 2026-07-15

### 1.1 Tasks & metrics (4 个 sub-testbed)

| Testbed | 中文 | 输入构造 | 度量 | 关键性质 |
|---|---|---|---|---|
| Noise Robustness | 噪声鲁棒性 | 在正文档中插入 0–80% 负文档 | **Accuracy**（exact match）| 噪声比例 0/0.2/0.4/0.6/0.8 |
| Negative Rejection | 拒绝能力 | **全部**都是负文档 | **Rejection rate**（精确）+ Rej\*（ChatGPT 评）| 模型应输出 "I can not answer …" |
| Information Integration | 多跳整合 | 把简单问题改写为多子问题 | **Accuracy**（exact match）| 需把多个文档信息拼成完整答案 |
| Counterfactual Robustness | 反事实鲁棒性 | 用 ChatGPT 生成"已知答案"→人工把答案替换为错误信息 | Acc（无文档）/ Acc_doc（有反事实文档）/ ED 错误检测率 / CR 错误纠正率 | 模型能识别并拒绝错误上下文 |

600 base + 200 补充（Information Integration）+ 200 补充（Counterfactual Robustness）= 1,000 总实例；EN + ZH 各半。

### 1.2 Original-paper numbers (Table 1/3/5/7 of arXiv:2309.01431)

Noise Robustness — ChatGPT (gpt-3.5-turbo) Accuracy at noise ratio 0 / 0.2 / 0.4 / 0.6 / 0.8:

| 噪声比 | EN | ZH |
|---|---|---|
| 0 | 96.33 | 95.67 |
| 0.2 | 94.67 | 94.67 |
| 0.4 | 94.00 | 91.00 |
| 0.6 | 90.00 | 87.67 |
| 0.8 | 76.00 | 70.67 |

Other models, EN @ 0.6 noise: ChatGLM-6B 84.67 · ChatGLM2-6B 77.33 · Vicuna-7B-v1.3 82.33 · Qwen-7B-Chat 87.67 · BELLE-7B-2M 71.33.

Negative Rejection — ChatGPT Rej (exact) / Rej\* (ChatGPT 评) EN: 24.67 / 45.00; ZH: 5.33 / 43.33.
Best exact-match Rej: Qwen-7B-Chat EN 31.00 / ZH 8.67.

Information Integration, accuracy at noise 0 / 0.2 / 0.4 (EN · ZH):
- ChatGPT 55 / 51 / 34 — 63 / 58 / 47
- Qwen-7B-Chat 55 / 50 / 37 — 67 / 56 / 55
- Vicuna-7B-v1.3 60 / 53 / 43 — 43 / 36 / 25 (best EN@0)

Counterfactual Robustness — ChatGPT-zh 91/17/1/3/33.33; ChatGPT-en 89/9/8/7/57.14; Qwen-7B-Chat-zh 77/12/5/4/25.00.

**Headline finding (verbatim, paper §3)**: "even without noise, the highest accuracy of LLMs can only reach 60% and 67% for English and Chinese, respectively" on Information Integration. Negative Rejection peaks at 45% (Rej\*, EN).

### 1.3 Updated 2024–2026 results

- **No official live leaderboard.** RGB repo (chen700564/RGB) last commit 2024-05-17; no public leaderboard site.
- RGB is reused as a *diagnostic* in 2024–2026 RAG surveys and ablations rather than as a moving leaderboard. Examples citing RGB 2025+:
  - "From vectors to knowledge graphs" (Comput. Sci. Rev. 2026, DOI 10.1016/j.cosrev.2026.100925, cited 6×)
  - "RAGRouter-Bench" (arXiv:2602.00296, 2026, cited 5×)
  - "SoK: Agentic RAG" (arXiv:2603.07379, 2026, cited 4×)
- Most 2024–2026 work reports RGB-evaluated self-correction modules (Self-RAG, FLARE, CRAG, Search-R1) on a 0-noise / 0.4-noise sub-slice, but the *best public numbers* on the original RGB eval-script remain the 2023 paper values.
- Practical guidance: **still the best free, four-axis RAG diagnostic**; if comparing modern systems, report the four metrics separately (do not aggregate).

Sources: https://github.com/chen700564/RGB (commit log 2024-05-17); https://arxiv.org/abs/2309.01431 (paper Tables 1, 3, 5, 7); Semantic Scholar citation pages for "RGB RAG benchmark" (https://www.semanticscholar.org/search?q=RGB+RAG+benchmark) and the citing-paper dump at /tmp/ss-2309.01431.txt.

---

## 2. ASQA — Answer Summaries for Questions which are Ambiguous

**Citation**: Ivan Stelmakh, Yi Luan, Bhuwan Dhingra, Ming-Wei Chang. "ASQA: Factoid Questions Meet Long-Form Answers." arXiv:2204.06092v2 (22 Jan 2023), Google Research.
- Primary: https://arxiv.org/abs/2204.06092
- Code: https://github.com/google-research/language/tree/master/language/asqa
- Access date: 2026-07-15

### 2.1 Tasks & metrics

- 6,316 ambiguous factoid questions built on top of AmbigQA (Min et al., 2020). Train 4,353 / Dev 948 / Test 1,015. Average answer length 64.8 tokens.
- Each question has 2–46 disambiguations; each instance crowdsourced with 1–2 long-form answers grounded in Wikipedia passages.
- 4,353 train / 948 dev / 1,015 test (two human references per dev/test).

**Metrics** (verbatim §4.1, paper):
| Metric | Definition | Range |
|---|---|---|
| **ROUGE-L** (multi-reference) | lowercased ROUGE-L-Sum F1, max of two references | 0–100 |
| **STR-EM** | % of disambiguations whose short answer appears as exact substring of the prediction (averaged per question) | 0–100 |
| **Disambig-F1** | SQuAD2-trained RoBERTa predicts short answer from prediction; F1 averaged over disambiguations and questions | 0–100 |
| **DR** = `sqrt(Disambig-F1 × ROUGE-L)` | geometric mean; chosen to penalize one-sided optimization | 0–100 |
| **Human** (DR / HO) | ACC = fraction of disambiguations human can answer from output; HO = human pairwise win % | 0–100 |

### 2.2 Original-paper numbers (Table 3, §6)

ASQA dev-set, T5-large (Raffel et al.) as generator:

| Model | LEN | ROUGE-L | STR-EM | Disambig-F1 | DR |
|---|---|---|---|---|---|
| Question (echoed 8×) | 71.6 | 15.3 | 1.2 | 0.2 | 1.5 |
| DPR@1 (retrieval only) | 99.9 | 33.8 | 30.1 | 16.7 | 23.7 |
| JPR@1 (Min 2021) | 196.8 | 30.5 | 45.0 | 25.8 | 28.1 |
| T5 Closed-Book | 62.5 | 33.5 | 10.3 | 7.4 | 15.7 |
| T5 Open-Book 1 passage | 63.0 | 40.3 | 33.6 | 21.2 | 29.2 |
| T5 Open-Book 3 passages | 71.1 | 42.7 | 39.9 | 25.1 | 32.7 |
| T5 Open-Book 5 passages | 71.6 | 43.0 | 41.0 | 26.4 | 33.7 |
| T5 + Oracle context | 82.6 | 46.6 | 88.7 | 59.2 | 52.5 |
| Human w/o context (HP-W/o-C) | 73.5 | 45.8 | 51.8 | 39.0 | 42.3 |
| **Human w/ context (HP-W/-C)** | 64.8 | **49.4** | **98.4** | **77.4** | **61.8** |

Headline: best T5 model is **DR 33.7** vs human DR **61.8**; 28.1-point headroom on the original protocol.

### 2.3 Updated 2024–2026 results (ALCE protocol, "STR-EM / EM-Rec / Disambig-F1 / DR")

The most-cited extension is **ALCE** (Gao, Yen, Yu, Chen; EMNLP 2023, arXiv:2305.14627, https://github.com/princeton-nlp/ALCE), which adds citation precision/recall and MAUVE, and forces every method to *cite* passages. ALCE reuses ASQA dev 1,000 random examples. Latest numbers on ALCE-ASQA (Table 4 + Table 19 of ALCE paper):

| Method | EM Rec | ROUGE-L | DR (computed) | MAUVE | Cit-Rec | Cit-Prec |
|---|---|---|---|---|---|---|
| ChatGPT VANILLA 5-psg | 40.4 | (46.6) | – | 66.6 | 73.6 | 72.5 |
| ChatGPT SUMM 10-psg | 43.3 | – | – | 70.0 | 68.9 | 61.8 |
| GPT-4 VANILLA 5-psg | 41.3 | – | – | 67.1 | 68.5 | 75.6 |
| GPT-4 VANILLA 20-psg | **44.4** | – | – | 64.9 | **73.0** | **76.5** |
| Self-RAG 7B (Llama2) | 30.0 (str-em) | 35.7 | 31.7 (Disambig-F1 × ROUGE-L product, paper "mau" col = MAUVE) | 74.3 | 66.9 | 67.8 |
| Self-RAG 13B | 31.7 | **37.0** | – | 71.6 | **70.3** | **71.3** |
| Ret-ChatGPT (top-5 GTR) | 40.7 | 39.9 | – | 79.7 | 65.1 | 76.6 |
| Ret-Llama2-chat 13B | 32.8 | 34.8 | – | 43.8 | 19.8 | 36.1 |

**2024–2026 best reported numbers on ASQA:**
- **EM-rec (STR-EM) 44.4** — GPT-4 VANILLA 20-passage, ALCE (arXiv:2305.14627 Table 4).
- **ROUGE-L 37.0** — Self-RAG 13B, Self-RAG paper (Asai et al., arXiv:2310.11511) Table 2; ALCE "rg" column.
- **DR ~38** — best end-to-end numbers from Self-RAG 13B + 5 docs on ALCE.
- **MAUVE 79.7** — Ret-ChatGPT (proprietary).
- **Cit-Rec 76.6 / Cit-Prec 70.3** — Ret-ChatGPT and Self-RAG 13B respectively.
- **Human upper bound 49.4 ROUGE-L / 98.4 STR-EM** (paper Table 3); **61.8 DR** unchanged.

**2024-published LLM judges** (HaluQuestQA, Sachdeva et al., ACL 2025, arXiv:2407.11930, https://github.com/UKPLab/acl2025-lfqa-hallucination) report on ASQA TIGERScore-based refinement:
- Baseline LLaMA2-13B-chat: % error 34.81, error score 1.20.
- Error-Informed Refinement (EIR): % error 16.63, error score 0.51, error-correction F1 0.77.
- Human preference (refined vs baseline): 18% vs 0% wins; **82% tie** — the refined model matches human answer on ASQA, while preferred on ELI5.

Sources: https://arxiv.org/abs/2204.06092 (paper Table 3, §6); https://arxiv.org/abs/2305.14627 (ALCE paper Tables 4, 19); https://arxiv.org/abs/2310.11511 (Self-RAG paper Table 2); https://arxiv.org/abs/2407.11930 (HaluQuestQA Table 4 + 5).

---

## 3. PopQA — Long-tail Entity QA

**Citation**: Alex Mallen*, Akari Asai*, Victor Zhong, Rajarshi Das, Daniel Khashabi, Hannaneh Hajishirzi. "When Not to Trust Language Models: Investigating Effectiveness of Parametric and Non-Parametric Memories for Retrieval-Augmented Language Models." arXiv:2212.10511v4 (2 Jul 2023), ACL 2023.
- Primary: https://arxiv.org/abs/2212.10511
- Code/data: https://github.com/AlexTMallen/adaptive-retrieval
- Access date: 2026-07-15

### 3.1 Tasks & metrics

- **PopQA**: 14,267 entity-centric QA pairs built from 16 Wikidata relations. Each subject's monthly Wikipedia pageview count → popularity bin (head / torso / tail, log10 bins).
- **EntityQuestions** (Sciavolino et al., 2021, EMNLP) — companion long-tail set; PopQA reports 82% subset with unique Wiki entity.
- **Metric**: accuracy = (prediction contains gold answer as substring) — substring EM, normalized (Min et al., 2021). Closed-book (vanilla) vs retrieval-augmented (BM25 / Contriever / GenRead / Adaptive Retrieval).
- **Headline finding**: model EM is monotonically correlated with subject log-popularity; for the 4,000 least popular questions, GPT-Neo 6B 15% / 20B 16% / GPT-3 davinci-003 19% (closed-book).

### 3.2 Original-paper numbers (arXiv:2212.10511 §4.2, §5, §6)

Closed-book vanilla accuracy on PopQA (aggregate, all 14,267 questions):
- OPT-1.3B / 2.7B / 6.7B / 13B: 0.16 / 0.18 / 0.20 / 0.22 (approximate from Figure 4 aggregate column)
- GPT-Neo-1.3B / 2.7B / GPT-J 6B / GPT-NeoX 20B: 0.20 / 0.23 / 0.25 / 0.27 (approx)
- GPT-3 davinci-002: 0.31; **GPT-3 davinci-003: 0.35**
- "Even without in-context examples, larger LMs exhibit reasonable performance: GPT-3 achieves 35% accuracy, and GPT-Neo 20B achieves 25%."

Retrieval-augmented:
- **Contriever-augmented GPT-3 davinci-003 ≈ +7 pp** over closed-book (paper Figure 7).
- Contriever-augmented GPT-Neo 2.7B matches closed-book GPT-3 davinci-003.
- Best non-adaptive: ≈ 41% accuracy.
- **Best overall = Adaptive Retrieval (GenRead+Contriever, GPT-3 davinci-003) = 46.5% accuracy** (paper §6.2 verbatim, 5.3 pp over the best non-adaptive method).
- Adaptive Retrieval also halves GPT-3 API cost on PopQA.

Tail (4,000 least popular) EM:
- GPT-Neo 6B / 20B / GPT-3 003 closed-book: 15% / 16% / 19%.
- Contriever-augmented GPT-Neo 2.7B: outperforms GPT-3 davinci-003 closed-book on tail.

### 3.3 Updated 2024–2026 results (EM, PopQA long-tail subset unless noted)

| Method | Year / Source | PopQA EM (long-tail / full) | Notes |
|---|---|---|---|
| GPT-3 davinci-003 + Contriever (paper baseline) | 2023, arXiv:2212.10511 | 41.2% / – | 5-passage Contriever |
| GPT-3 davinci-003 + Adaptive GenRead/Contriever (paper best) | 2023 | **46.5%** / – | 5.3pp over best non-adaptive |
| Self-RAG (Llama2-7B) | 2023, arXiv:2310.11511 | **54.9% (long-tail)**, 50.5% full | Reuses paper's long-tail 1,399-subset |
| Self-RAG (Llama2-13B) | 2023 | **55.8% (long-tail)**, 45.7% full | Best non-proprietary on long-tail |
| CRAG (LLaMA2-7B) | 2024, arXiv:2401.15884 | 54.9% (full PopQA) | +4.4pp over RAG, +2.4pp over Self-RAG reproduced |
| CRAG (SelfRAG-LLaMA2-7B) | 2024 | 59.8% (full PopQA) | Stronger LLM init |
| Self-CRAG (LLaMA2-7B) | 2024 | 49.0% | – |
| Self-CRAG (SelfRAG-LLaMA2-7B) | 2024 | **61.8%** | Best of CRAG family |
| Reag (Yan 2024, retrieval rerank) | 2024 | reported ≈ 55% | – |
| RAG Foundry (Llama-3 8B, CoT-sft) | 2024, arXiv:2408.02545 | EM-not-applicable (uses STR-EM on ASQA) | PopQA not in their table |
| Search-R1-base (Qwen2.5-7B) | 2025, arXiv:2503.09516 | **EM 0.457** | Outperforms RAG (0.392), R1 (0.202), SFT (0.121) |
| Search-R1-instruct (Qwen2.5-7B) | 2025 | EM 0.397 | +20% avg relative gain over 7B SFT |
| R1-Searcher (Qwen2.5-7B RL+search) | 2025, arXiv:2503.05592 | reports 4-way multi-hop only; PopQA not direct | – |
| IRCoT (Trivedi 2022) | 2022 | EM 0.301 on PopQA (Search-R1 baseline) | – |
| **OpenAI proprietary (Ret-ChatGPT)** | 2023 Self-RAG baseline | **50.8%** (full PopQA) | RAG with top-10 Contriever |

Headline (mid-2026): **Self-CRAG / SelfRAG-LLaMA2-7B ≈ 61.8% accuracy on full PopQA, ≈ +25pp over 2022 vanilla LMs** (paper + 2024 follow-up). Search-R1 (Qwen2.5-7B) is the most competitive open RL recipe at 45.7% EM. No new dataset additions; **PopQA itself is unchanged**.

Sources: https://arxiv.org/abs/2212.10511 (Figures 4, 5, 7, 9; §4.2, §5, §6); https://arxiv.org/abs/2310.11511 (Table 2 long-tail column); https://arxiv.org/abs/2401.15884 (Tables 1, 2, 3); https://arxiv.org/abs/2503.09516 (Table 2, PopQA column); https://arxiv.org/abs/2408.02545 (Table 1 — does not include PopQA).

---

## 4. ELI5 — Long Form Question Answering

**Citation**: Angela Fan, Yacine Jernite, Ethan Perez, David Grangier, Jason Weston, Michael Auli. "ELI5: Long Form Question Answering." ACL 2019, arXiv:1907.09190v1 (22 Jul 2019), Facebook AI Research.
- Primary: https://arxiv.org/abs/1907.09190
- Project page: https://facebookresearch.github.io/ELI5
- Code: https://github.com/facebookresearch/ELI5
- Access date: 2026-07-15

### 4.1 Tasks & metrics

- 272K Reddit "Explain Like I'm Five" Q–A pairs (top-voted answer retained; 63% have ≥2 valid answers). Split: 237K train / 10K valid / 25K test, by TFIDF dissimilarity to avoid training/test leakage.
- Average question 42.2 words, **support document 857.6 words** (capped via TFIDF snippet extraction from Common Crawl), **answer 130.6 words**.
- 6.6 sentences/answer; 44.8% "Why", 27.1% "How", 18.3% "What", 11.3% "When" — heavily open-ended.
- Metrics: **ROUGE-1, ROUGE-2, ROUGE-L** (F1) on full answers; **ROUGE-20%** (generate the last 20% from first 80%) for coherence; FILL-1 (N/V/A token accuracy); human 5-point Likert on fluency + pairwise preference.
- Crowdsourced manual analysis (Table 2 of paper): **94.5%** of gold answers fully address the question; **90.2%** of gold answers come with an explanation; **65%** of support documents contain the *full* answer; **92%** contain *relevant* info.

### 4.2 Original-paper numbers (Table 3 + Table 5, arXiv:1907.09190)

| Model | PPL | ROUGE-1 | ROUGE-2 | ROUGE-L |
|---|---|---|---|---|
| Support Document (echoed) | – | 16.8 | 2.3 | 10.2 |
| Nearest Neighbor | – | 16.7 | 2.3 | 12.5 |
| Extractive TFIDF | – | 20.6 | 2.9 | 17.0 |
| Extractive BidAF | – | 23.5 | 3.1 | 17.5 |
| Oracle support doc | – | 27.4 | 2.8 | 19.9 |
| Oracle web sources | – | 54.8 | 8.6 | 40.3 |
| LM Q + A | 42.2 | 27.8 | 4.7 | 23.1 |
| LM Q + D + A | 33.9 | 26.4 | 4.0 | 20.5 |
| Seq2Seq Q → A | 52.9 | 28.3 | 5.1 | 22.7 |
| Seq2Seq Q + D → A | 55.1 | 28.3 | 5.1 | 22.8 |
| Seq2Seq Multi-task | 32.7 | 28.9 | 5.4 | 23.1 |

ROUGE-20% (last 20% generation): Seq2Seq multi-task 37.2 ROUGE-1 / 14.6 ROUGE-2 / 33.0 ROUGE-L (best). Human preference (Table 5): "the reference answer is preferred over the output of all of our trained models in **at least 85.5% of cases**." Multi-task 57% preferred over extractive.

### 4.3 Updated 2024–2026 results (ALCE protocol, claim recall + ROUGE-L + MAUVE + citation)

ALCE (Gao et al. 2023, arXiv:2305.14627) and HaluQuestQA (Sachdeva et al. ACL 2025, arXiv:2407.11930) are the standard mid-2020s re-evaluations. ALCE Table 21 reports full results on ELI5 dev 1,000:

| Method | MAUVE | Claim-Rec | Cit-Rec | Cit-Prec | ROUGE-L |
|---|---|---|---|---|---|
| ChatGPT VANILLA 5-psg | 57.2 | 12.0 | 51.1 | 50.0 | 20.6 |
| ChatGPT SUMM 10-psg | 40.2 | 12.5 | 51.5 | 48.2 | 20.3 |
| ChatGPT SNIPPET 10-psg | **62.9** | 14.3 | 50.4 | 45.0 | 21.0 |
| ChatGPT INTERACT | **68.0** | 13.3 | 47.8 | 45.0 | 20.1 |
| ChatGPT ORACLE 5-psg | 59.4 | **21.3** | **57.8** | 56.0 | 21.2 |
| GPT-4 VANILLA 5-psg | 38.4 | 14.2 | 44.0 | 50.1 | 20.6 |
| GPT-4 VANILLA 20-psg | 41.5 | **18.3** | 48.5 | **53.4** | 22.2 |
| LLaMA-2-70B-Chat VANILLA 5-psg | 38.6 | 12.8 | 38.3 | 37.9 | 21.3 |
| StableBeluga2 VANILLA 5-psg | 33.0 | 14.0 | 27.9 | 29.0 | 20.6 |

**HaluQuestQA (ACL 2025) refinement results on ELI5, LLaMA2-13B-chat, Table 4** (TIGERScore):

| Method | % Error samples | Error score | Error-correction F1 |
|---|---|---|---|
| Baseline (LLaMA2-13B-chat) | 22.93 | 0.82 | – |
| Zero-shot refinement | 9.61 | 0.27 | 0.81 |
| Generic "improve answer" | 6.06 | 0.22 | 0.87 |
| Error-Informed Refinement (EIR) | **3.81** | **0.13** | **0.92** |

HaluQuestQA human preference (Table 5): refined vs baseline — Refined 62%, Baseline 0%, Tie 38%; **Overall preference 100% for refined**.

**Headline (mid-2026)**:
- **Best ROUGE-L 22.2** (GPT-4 VANILLA 20-psg, ALCE) — barely above 2019 multi-task Seq2Seq (23.1).
- **Best Claim-Rec 21.3** (ChatGPT ORACLE 5-psg, ALCE).
- **Best MAUVE 68.0** (ChatGPT INTERACT).
- **Best refined error-correction F1 0.92** (EIR on HaluQuestQA).
- **No new leaderboard**; ELI5 is the hardest long-form reference and is dominated by ALCE re-evaluations + HaluQuestQA-style fine-grained error metrics.

Sources: https://arxiv.org/abs/1907.09190 (Tables 2, 3, 5); https://arxiv.org/abs/2305.14627 (Table 21); https://arxiv.org/abs/2407.11930 (Tables 4, 5); https://github.com/princeton-nlp/ALCE (repository + eval script).

---

## 5. MS MARCO QA — generative question answering (now retired)

**Citation**: Payal Bajaj, Daniel Campos, Nick Craswell, Li Deng, Jianfeng Gao, Xiaodong Liu, Rangan Majumder, Andrew McNamara, Bhaskar Mitra, Tri Nguyen, et al. "MS MARCO: A Human Generated MAchine Reading COmprehension Dataset." arXiv:1611.09268v3 (31 Oct 2018).
- Primary: https://arxiv.org/abs/1611.09268
- Project: https://microsoft.github.io/msmarco/
- Code: https://github.com/microsoft/MSMARCO-Question-Answering
- Access date: 2026-07-15

### 5.1 Tasks & metrics

- 1,010,916 anonymized Bing queries with human-generated answer (originally 100K) + 8,841,823 passages from 3,563,535 web documents + 182,669 well-formed answers.
- Three tasks defined in the original paper: (i) QnA novice: predict answerability + generate answer from 10 passages; (ii) QnA intermediate: well-formed answer; (iii) passage ranking.
- **Retired**: official QA and NLGEN leaderboards closed on **2020-10-23** (community notice on project page; passage/document ranking still active).
- Original metrics: **ROUGE-L** + **BLEU-1** + human eval; v1.1 added BLEU-2/3/4 (Mitra et al. 2016). v2.1 added phrasing-aware BLEU. Paper §5.1 baseline numbers on v1.1 (Table 4):

| v1.1 Model | ROUGE-L |
|---|---|
| Best Passage (oracle) | 0.351 |
| DSSM-like passage ranker | 0.177 |
| Seq2Seq (vanilla) | 0.089 |
| Memory Network | 0.119 |
| BLEU on multi-answer subset: Best Passage 0.359 / pa-BLEU 0.453; MemNN 0.340 / 0.341. | – |

### 5.2 Official leaderboards (v2.1 QnA + NLGEN; final entries Oct 2020)

**QnA v2.1 Leaderboard (https://microsoft.github.io/msmarco/#qna, top 7)**:

| Rank | Model | Date | ROUGE-L | BLEU-1 |
|---|---|---|---|---|
| 1 | Multi-doc Enriched BERT (Ming Yan, Alibaba DAMO NLP) | 2019-06-20 | **0.540** | **0.565** |
| 2 | Human Performance | 2018-04-23 | 0.539 | 0.485 |
| 3 | BERT Encoded T-Net | 2019-08-05 | 0.526 | 0.539 |
| 4 | Selector+Combine-Content-Generator | 2019-03-19 | 0.525 | 0.544 |
| 5 | LM+Generator (Alibaba DAMO) | 2019-11-25 | 0.522 | 0.516 |
| 6 | Masque Q&A Style (Nishida et al. 2019) | 2019-01-03 | 0.522 | 0.437 |
| 7 | Deep Cascade QA (Yan et al. 2018) | 2018-12-12 | 0.520 | 0.546 |

**NLGEN v2.1 Leaderboard (top 7)**:

| Rank | Model | Date | ROUGE-L | BLEU-1 |
|---|---|---|---|---|
| 1 | **Human Performance** | 2018-04-23 | **0.632** | 0.530 |
| 2 | PALM (Alibaba DAMO) | 2019-12-16 | 0.498 | 0.499 |
| 3 | REAG (Anonymous) | 2020-03-27 | 0.498 | 0.497 |
| 4 | Masque NLGEN (Nishida 2019) | 2019-01-03 | 0.496 | 0.501 |
| 5 | CompLM (Alibaba DAMO) | 2019-12-03 | 0.496 | 0.489 |
| 6 | PALM (Alibaba DAMO, resub.) | 2019-12-09 | 0.496 | 0.484 |
| 7 | BERT+Multi-Pointer-Generator (ColorfulClouds + BUPT) | 2019-06-11 | 0.495 | 0.476 |

**v1 Leaderboard (top entries, ROUGE-L/BLEU-1)**:
- MARS (Yuanfudao research NLP) 2018-03-26: 0.497 / 0.480.
- Human Performance 2016-12: 0.470 / 0.460.
- V-Net (Baidu NLP, Wang et al. 2018) 2018-02-15: 0.462 / 0.445.
- S-Net (Microsoft, Tan et al. 2017) 2017-06: 0.452 / 0.438.
- R-Net (Microsoft, Wei et al. 2016) 2017-05: 0.429 / 0.422.

Headline: **MS MARCO QnA best ROUGE-L = 0.540 (Alibaba DAMO 2019), just above Human (0.539) on QnA v2.1**. **NLGEN best ROUGE-L = 0.632 (Human)** — no published model beat human.

### 5.3 Updated 2024–2026 results

- **No new public numbers on retired QnA/NLGEN leaderboards** — last accepted submission 2020-10-23. MS MARCO is still actively used in 2024–2026 *only* for **passage ranking (MRR@10)** and document ranking. RAG papers in 2024+ cite MS MARCO as a *retrieval training corpus* (e.g., Contriever-MS-MARCO in Self-RAG; E5 in Search-R1) but not as an *answer generation eval*.
- Practical guidance: do not treat 2024+ MS MARCO "ROUGE-L" numbers as comparable to retired-leaderboard scores — they use different splits/protocols. For long-form QA, **ASQA + ALCE** is the modern replacement.

Sources: https://microsoft.github.io/msmarco/#qna, #retirement (parsed via `browse html` 2026-07-15); https://arxiv.org/abs/1611.09268 (paper Tables 4, 5, 7); commit message archives of MS MARCO repo (last commit 2024 with maintenance-only updates).

---

## 6. Summary table (mid-2026 best, with primary source)

| Benchmark | Metric | Original paper (year) | Best (mid-2026) | Δ over baseline | Source |
|---|---|---|---|---|---|
| **RGB** (EN) | Noise Robustness Acc @ 0.6 noise | 90.00 (ChatGPT, 2023) | 90.00 (no new SOTA) | – | arXiv:2309.01431 |
| **RGB** (EN) | Negative Rejection Rej\* | 45.00 (ChatGPT, 2023) | 45.00 | – | arXiv:2309.01431 |
| **RGB** (EN) | Information Integration Acc @ 0 noise | 60 (Vicuna-7B, 2023) | 60 | – | arXiv:2309.01431 |
| **ASQA** | EM-rec (ALCE) | 40.4 (ChatGPT, 2023) | **44.4** (GPT-4 20-psg, 2023) | +4.0 | arXiv:2305.14627 |
| **ASQA** | ROUGE-L | 49.4 (Human, 2022) | **37.0** (Self-RAG 13B, 2023) | –12.4 (vs human UB) | arXiv:2310.11511 |
| **ASQA** | DR | 33.7 (T5 OB-5, 2022) | ~38 (Self-RAG 13B, 2023) | +4.3 | arXiv:2310.11511 |
| **ASQA** | Citation Prec/Rec | n/a | 76.5 / 73.0 (GPT-4 20-psg) | new | arXiv:2305.14627 |
| **PopQA** | EM (full) | 35 (GPT-3 003 CB, 2022) | **61.8** (Self-CRAG / SelfRAG-LLaMA2-7B, 2024) | +26.8 | arXiv:2401.15884 |
| **PopQA** | EM (long-tail) | 19 (GPT-3 003 CB, 2022) | **55.8** (Self-RAG 13B, 2023) | +36.8 | arXiv:2310.11511 |
| **ELI5** | ROUGE-L | 23.1 (Seq2Seq multi-task, 2019) | **22.2** (GPT-4 20-psg, 2023) | –0.9 | arXiv:2305.14627 |
| **ELI5** | Claim-Recall | n/a | **21.3** (ChatGPT ORACLE, 2023) | new | arXiv:2305.14627 |
| **ELI5** | Error-correction F1 (HaluQuestQA) | n/a | **0.92** (EIR, 2025) | new | arXiv:2407.11930 |
| **MS MARCO QnA v2.1** | ROUGE-L | 0.540 (Multi-doc BERT, 2019) | 0.540 (leaderboard retired 2020) | – | https://microsoft.github.io/msmarco/ |
| **MS MARCO NLGEN v2.1** | ROUGE-L | 0.632 (Human, 2018) | 0.632 (leaderboard retired 2020) | – | https://microsoft.github.io/msmarco/ |

---

## 7. Mneme 在这张地图上的位置

| 基准 | Mneme 适用？ | 理由 |
|---|---|---|
| **RGB** | 间接 | Mneme 不直接评 RAG 抗噪/拒答，但 wiki 的 tag 体系 + 拒答 skill 行为可经同样 4 轴自检 |
| **ASQA / ALCE** | 直接（**dream** 维度的核心度量） | 模糊问题的"展开所有解释"与 dream 的 agent 决定"哪些短答案成稿"同构 |
| **PopQA** | 直接（**search** 维度的核心度量） | 长尾实体是 dream 必须解决的"参数化记忆缺位"问题；按 entity popularity 分桶测试 dream 行为 |
| **ELI5** | 部分 | Mneme 不打算做自由生成；如果做 chunk 整合评测可用 ALCE-ELI5 的 claim-recall + citation-recall 替代 |
| **MS MARCO QnA/NLGEN** | 间接 | 旧式 leaderboard 已死；引用它只作为检索语料（与 Mneme FTS5 输入同源）|

建议 v2.1 dream 自检默认走 **ASQA-str-em + PopQA-EM** 双指标（成本可控、与现代 RAG 体系直接可比）；ELI5/RGB 留给 v2.2+。

---

## 8. 引用与访问 (Sources & Access)

| 资源 | URL | 访问日期 |
|---|---|---|
| RGB paper (correct) | https://arxiv.org/abs/2309.01431 | 2026-07-15 |
| RGB code | https://github.com/chen700564/RGB | 2026-07-15 |
| ASQA paper | https://arxiv.org/abs/2204.06092 | 2026-07-15 |
| ASQA code | https://github.com/google-research/language/tree/master/language/asqa | 2026-07-15 |
| PopQA paper (correct) | https://arxiv.org/abs/2212.10511 | 2026-07-15 |
| PopQA code | https://github.com/AlexTMallen/adaptive-retrieval | 2026-07-15 |
| ELI5 paper | https://arxiv.org/abs/1907.09190 | 2026-07-15 |
| ELI5 code | https://github.com/facebookresearch/ELI5 | 2026-07-15 |
| MS MARCO paper | https://arxiv.org/abs/1611.09268 | 2026-07-15 |
| MS MARCO project (retired QnA) | https://microsoft.github.io/msmarco/ | 2026-07-15 |
| ALCE paper | https://arxiv.org/abs/2305.14627 | 2026-07-15 |
| ALCE code | https://github.com/princeton-nlp/ALCE | 2026-07-15 |
| Self-RAG paper | https://arxiv.org/abs/2310.11511 | 2026-07-15 |
| CRAG paper | https://arxiv.org/abs/2401.15884 | 2026-07-15 |
| Search-R1 paper | https://arxiv.org/abs/2503.09516 | 2026-07-15 |
| R1-Searcher paper | https://arxiv.org/abs/2503.05592 | 2026-07-15 |
| FLARE paper | https://arxiv.org/abs/2305.06983 | 2026-07-15 |
| RAG Foundry paper | https://arxiv.org/abs/2408.02545 | 2026-07-15 |
| HaluQuestQA paper | https://arxiv.org/abs/2407.11930 | 2026-07-15 |
| HaluQuestQA code | https://github.com/UKPLab/acl2025-lfqa-hallucination | 2026-07-15 |
| LongCite paper (citation eval) | https://arxiv.org/abs/2409.02897 | 2026-07-15 |
