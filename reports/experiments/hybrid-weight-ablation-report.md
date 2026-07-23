# Hybrid Weight Comparison and Ablation Report

> **Superseded:** deployment decisions now use `hybrid-weight-nested-cv-report.md`.

> Generated 2026-07-23T12:49:14.045215+00:00 from the active local bundle. Protocol: `reports/designs/2026-07-23-hybrid-weight-ablation.md`.

## Executive conclusion

Validation selected **Graph/FTS5/L2 = 0.60/0.35/0.05**. On the untouched holdout, its family-macro MRR@10 was **0.788**, versus **0.779** for 0.40/0.40/0.20 (delta +0.009) and **0.810** for the strongest pair `Tuned Graph+L2` (triple delta -0.022).

The frozen deployment rule does not justify changing the current triple; it retains **0.40/0.40/0.20**.

## Holdout comparison

| Stage | Graph/FTS5/L2 | Family MRR | Title Hit@1 | Worst family | Hit@1 | Recall@3 | Recall@10 | Noisy MRR |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Graph only | 1.00/0.00/0.00 | 0.551 | 0.750 | 0.077 | 0.492 | 0.615 | 0.646 | 0.484 |
| FTS5 only | 0.00/1.00/0.00 | 0.108 | 0.500 | 0.000 | 0.085 | 0.117 | 0.117 | 0.029 |
| L2 only | 0.00/0.00/1.00 | 0.683 | 1.000 | 0.442 | 0.608 | 0.727 | 0.747 | 0.519 |
| Tuned Graph+FTS5 | 0.60/0.40/0.00 | 0.544 | 1.000 | 0.077 | 0.477 | 0.608 | 0.646 | 0.484 |
| Tuned Graph+L2 | 0.80/0.00/0.20 | 0.810 | 1.000 | 0.551 | 0.762 | 0.838 | 0.859 | 0.718 |
| Tuned FTS5+L2 | 0.00/0.50/0.50 | 0.705 | 1.000 | 0.442 | 0.638 | 0.735 | 0.758 | 0.545 |
| Equal triple | 0.33/0.33/0.33 | 0.774 | 1.000 | 0.551 | 0.692 | 0.828 | 0.859 | 0.696 |
| Current triple | 0.40/0.40/0.20 | 0.779 | 1.000 | 0.551 | 0.700 | 0.828 | 0.859 | 0.699 |
| Tuned triple | 0.60/0.35/0.05 | 0.788 | 1.000 | 0.564 | 0.723 | 0.833 | 0.859 | 0.702 |

## Query-family ablation

| Stage | Exact | Long phrase | Sentence | Typo | Omission |
|---|---:|---:|---:|---:|---:|
| Graph only | 0.846 | 0.862 | 0.077 | 0.333 | 0.634 |
| FTS5 only | 0.365 | 0.115 | 0.000 | 0.000 | 0.058 |
| L2 only | 0.808 | 0.917 | 0.654 | 0.442 | 0.596 |
| Tuned Graph+FTS5 | 0.814 | 0.862 | 0.077 | 0.333 | 0.634 |
| Tuned Graph+L2 | 0.981 | 0.981 | 0.654 | 0.551 | 0.885 |
| Tuned FTS5+L2 | 0.846 | 0.936 | 0.654 | 0.442 | 0.647 |
| Equal triple | 0.885 | 0.942 | 0.654 | 0.551 | 0.840 |
| Current triple | 0.885 | 0.962 | 0.654 | 0.551 | 0.846 |
| Tuned triple | 0.885 | 1.000 | 0.654 | 0.564 | 0.840 |

## Robustness and uncertainty

The tuned triple's query-bootstrap holdout MRR 95% interval is [0.726, 0.848]. The paired tuned-minus-current interval is [-0.014, +0.032]. The paired tuned-minus-best-pair interval is [-0.047, +0.003], so the pair's -0.022 point advantage is not significant.

Clean-to-noisy MRR change for the tuned triple is -0.144. Query-leg errors: 0.

## Dataset and environment

- Bundle: `/Users/scott1743/Desktop/mneme_wiki` (9 indexed concept pages)
- Enriched vocabulary: 28 eligible entities; 7 page-title controls; 59 base cases; 295 generated queries
- Split: 165 validation queries / 130 holdout queries, grouped by base case
- Mneme 4.7.0; Python 3.13.0; model `BAAI/bge-small-zh-v1.5`
- Grid: 0.05; top-k: 10; candidate pool: 100; bootstrap: 5000

## Interpretation limits

This is a small, construction-aware local diagnostic: entity queries and labels originate in the approved enrichment manifest, while title controls come from its authoritative Markdown source pages. The corpus has few concept pages. It measures ranking behavior for the current CRM vocabulary, not general search quality. Re-run after substantial corpus growth, enrichment changes, embedding-model changes, or scoring changes. The machine-readable payload retains every generated query, candidate ranking, error, index hash, validation-selected pair, and metric.
