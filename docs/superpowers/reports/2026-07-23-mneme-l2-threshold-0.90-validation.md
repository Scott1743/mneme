---
type: Report
title: Mneme L2 distance 0.90 validation
description: Before/after relevance-gate validation on the active 163-page wiki.
timestamp: 2026-07-23
---

# Mneme L2 Distance 0.90 Validation

## Conclusion

Changing the default `BAAI/bge-small-zh-v1.5` L2 distance boundary from
`1.10` to `0.90` materially improves no-answer behavior on this corpus without
reducing the measured related-query ranking:

| Metric | Distance 1.10 | Distance 0.90 | Delta |
|---|---:|---:|---:|
| Recall@5, 10 related queries | 1.00 | 1.00 | 0.00 |
| MRR@10, 10 related queries | 0.85 | 0.85 | 0.00 |
| Empty-result rate, 10 unrelated queries | 0.10 | 0.90 | +0.80 |

The requested query `吃饭` changes from 13 unrelated pages to an empty result.
The `0.90` boundary is accepted for this release line. It is a relevance gate,
not a complete out-of-domain classifier: `足球比赛结果` still produces one
false-positive page at distance `0.8622`.

## Setup

- Corpus: `/Users/scott1743/Desktop/mneme_wiki`
- Pages: 163
- Indexed chunks: 1,913
- Embedding model: `BAAI/bge-small-zh-v1.5`
- Vector metric: normalized-vector Euclidean distance; lower is better
- UI request limit: 20 pages
- Evaluation set: 10 labeled related queries and 10 deliberately unrelated
  Chinese queries
- Comparison method: obtain the same ordered candidates under the old `1.10`
  gate, then apply `0.90` to those recorded distances. No content or index was
  changed between the two measurements.

For normalized vectors, distance `0.90` corresponds to cosine similarity of
approximately `0.595` using `cosine = 1 - distance^2 / 2`.

## Related Queries

The expected page stayed in the top five for every labeled query. All expected
pages also remained below the new threshold.

| Query | Expected page | Rank | Distance |
|---|---|---:|---:|
| `注意力机制` | `sources/01_introduction/1.3_attention_birth.md` | 1 | 0.7224 |
| `Transformer 核心思想` | `sources/01_introduction/1.4_transformer_idea.md` | 1 | 0.8278 |
| `KV 缓存如何避免重复计算` | `sources/10_inference_optimization/10.2_kv_cache.md` | 1 | 0.4612 |
| `多头注意力为什么使用多个子空间` | `sources/02_attention/2.3_multi_head.md` | 1 | 0.5632 |
| `词嵌入把离散符号映射到连续向量` | `sources/03_components/3.2_embedding.md` | 1 | 0.6530 |
| `状态空间模型和混合架构` | `sources/14_future_trends/14.3_ssm_hybrid.md` | 1 | 0.7061 |
| `AI Agent 如何调用工具` | `sources/14_future_trends/14.5_agent_tool_use.md` | 2 | 0.7908 |
| `注意力的计算复杂度` | `sources/02_attention/2.5_complexity_limits.md` | 2 | 0.7179 |
| `缩放点积为什么除以根号 d` | `sources/02_attention/2.2_scaled_dot_product.md` | 1 | 0.6647 |
| `自注意力与交叉注意力区别` | `sources/02_attention/2.4_self_cross_causal.md` | 2 | 0.7184 |

## Unrelated Queries

| Query | Results at 1.10 | Results at 0.90 | Best old distance |
|---|---:|---:|---:|
| `吃饭` | 13 | 0 | 1.0362 |
| `今天天气怎么样` | 5 | 0 | 0.9677 |
| `红烧肉怎么做` | 3 | 0 | 1.0656 |
| `足球比赛结果` | 20 | 1 | 0.8622 |
| `北京三日游` | 9 | 0 | 1.0487 |
| `股票明天涨吗` | 15 | 0 | 1.0448 |
| `如何给猫洗澡` | 0 | 0 | > 1.10 |
| `推荐一部爱情电影` | 2 | 0 | 1.0531 |
| `快递什么时候到` | 5 | 0 | 1.0512 |
| `健身减脂食谱` | 11 | 0 | 1.0425 |

The remaining false positive for `足球比赛结果` is
`sources/02_llm_basics/2.5_ssm_vs_transformer.md`. Its best chunk contains
generic language around query results and long-context retrieval, which the
embedding model places unusually close to the query despite the domain
mismatch. Tightening below `0.8622` would remove it, but would also reduce the
margin above valid results such as `Transformer 核心思想` at `0.8278`. A future
out-of-domain classifier or lexical/vector agreement rule is safer than using
this single sample to tighten the global threshold again.

## Verification Gates

| Gate | Target | Result | Status |
|---|---:|---:|---|
| Related Recall@5 | >= 0.85 | 1.00 | PASS |
| Related MRR@10 | >= 0.70 | 0.85 | PASS |
| Unrelated empty-result rate | >= 0.80 | 0.90 | PASS |
| `吃饭` returns no L2 candidates | required | 0 pages | PASS |

## Limitations

- The related set is small and intentionally anchored to known pages; it is a
  regression sample, not a production-scale retrieval benchmark.
- The unrelated set contains ten Chinese queries only. English, mixed-language,
  entity-ID, and cross-document synthesis behavior were not measured here.
- The comparison evaluates the threshold only. It does not compare query
  instructions, rerankers, hybrid retrieval, or a dedicated out-of-domain
  detector.
- Raw vector distance remains navigation evidence rather than factual
  authority; agents must still read the complete Markdown pages before use.
