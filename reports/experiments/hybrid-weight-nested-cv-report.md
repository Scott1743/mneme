# Hybrid Weight Nested Cross-Validation Report

> Generated 2026-07-23T13:06:12.621467+00:00. This report supersedes the single-split pilot for deployment decisions.

## Executive conclusion

The 1% all-data fit selected **0.75/0.10/0.15**. Across 10x5 grouped outer folds, the tuned procedure reached case-macro MRR@10 **0.818** versus **0.792** for 0.40/0.40/0.20. The paired case-cluster bootstrap delta was **+0.027** [+0.013, +0.041].

The preregistered rule recommends changing production to **0.75/0.10/0.15**.

## Out-of-fold comparison

| Stage | Case MRR | Family MRR | Worst family | Hit@1 | Recall@3 | Recall@10 | Noisy MRR |
|---|---:|---:|---:|---:|---:|---:|---:|
| Nested tuned triple | 0.818 | 0.818 | 0.631 | 0.759 | 0.853 | 0.876 | 0.737 |
| Nested tuned Graph+FTS5 | 0.538 | 0.548 | 0.034 | 0.475 | 0.606 | 0.635 | 0.500 |
| Nested tuned Graph+L2 | 0.817 | 0.817 | 0.632 | 0.756 | 0.856 | 0.876 | 0.741 |
| Nested tuned FTS5+L2 | 0.690 | 0.687 | 0.436 | 0.618 | 0.727 | 0.753 | 0.516 |
| Current triple | 0.792 | 0.789 | 0.624 | 0.705 | 0.850 | 0.876 | 0.729 |
| Equal triple | 0.788 | 0.785 | 0.621 | 0.701 | 0.850 | 0.876 | 0.725 |
| Graph only | 0.539 | 0.551 | 0.034 | 0.483 | 0.608 | 0.635 | 0.500 |
| FTS5 only | 0.102 | 0.106 | 0.000 | 0.090 | 0.101 | 0.101 | 0.013 |
| L2 only | 0.667 | 0.662 | 0.436 | 0.590 | 0.712 | 0.735 | 0.505 |

## Inference

- `triple_mrr`: +0.818 [+0.772, +0.863]
- `triple_vs_current`: +0.027 [+0.013, +0.041]
- `triple_vs_best_pair`: +0.001 [-0.004, +0.006]

## Weight stability

The triple tuner selected 6 distinct weights over 50 outer folds. Channel means were Graph 0.755, FTS5 0.094, L2 0.151; standard deviations were 0.025, 0.025, and 0.013.

Most frequent selections:

- `0.75/0.10/0.15`: 32/50 folds
- `0.80/0.04/0.16`: 7/50 folds
- `0.74/0.12/0.14`: 6/50 folds
- `0.68/0.12/0.20`: 2/50 folds
- `0.79/0.06/0.15`: 2/50 folds
- `0.75/0.14/0.11`: 1/50 folds

## Dataset and execution

- 59 base cases; 288 statistical queries; 7 exact-title contract rows
- Full triple grid: 4,851; pair grids: 297; repeats/folds: 10x5
- Query-leg errors: 0; model: `BAAI/bge-small-zh-v1.5`

## Limits

This remains a small construction-aware local benchmark over nine concept pages. Nested validation and case-cluster uncertainty prevent variant leakage and reduce tuning optimism, but they do not replace independent human queries or production search logs. Re-run after material corpus, enrichment, model, threshold, or scoring changes.
