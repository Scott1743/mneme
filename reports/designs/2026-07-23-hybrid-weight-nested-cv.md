# Hybrid Weight Nested Cross-Validation

> **Status**: frozen protocol · 2026-07-23
> **Purpose**: repeat the local Hybrid weight experiment with finer search,
> group-aware validation, and uncertainty measured at the independent case
> level.

## 1. Why this supersedes the pilot

The pilot used 0.05 weight increments, one 60/40 split, and query-level
bootstrap. Its 295 queries were generated as five variants of only 59 base
cases, so query-level resampling treated correlated variants as independent.
This protocol keeps the same audited retrieval corpus and query construction
but fixes those statistical weaknesses.

## 2. Data and independence unit

Queries come from approved enriched entities, stable same-page entity pairs,
and enrichment source-page titles. Each base case produces `exact`,
`long_phrase`, `sentence`, `typo`, and `omission` variants.

The **base case** is the unit of splitting and uncertainty. All variants of one
case always stay in the same fold. The seven exact source-page-title queries
form a deterministic product contract: every selected weight must maximize
their Hit@1, and these seven rows are excluded from inferential metrics because
they participate in selection.

## 3. Weight search and nested evaluation

- Full three-way Hybrid exhaustively searches every positive 0.01-simplex
  point: 4,851 Graph/FTS5/L2 combinations.
- Each two-way ablation searches 99 positive 0.01 mixtures, 297 total.
- Graph-only, FTS5-only, L2-only, equal triple, and current 0.40/0.40/0.20 are
  fixed controls.
- Ten deterministic repeats of stratified grouped 5-fold cross-validation are
  used. Base cases are stratified by `entity`, `pair`, and `title` source.
- In each outer fold, weights are selected using only the other four folds.
  The selected weights then score the held-out base cases. Every statistical
  query therefore receives ten out-of-fold predictions.

Selection is lexicographic: exact-title contract Hit@1, training
family-macro MRR@10, training worst-family MRR@10, Recall@3, then proximity to
the current triple for full Hybrid or equal weighting for a pair. Remaining
ties prefer larger L2 and then larger FTS5 weight. The same rule fits a final
candidate on all base cases only after out-of-fold evaluation is complete.

## 4. Metrics and uncertainty

- Base-case macro MRR@10 is primary: average variants inside each case, then
  average cases.
- Family-macro MRR@10, worst-family MRR@10, Hit@1, Recall@3, Recall@10, clean
  MRR, and noisy MRR are secondary.
- Selected-weight frequency, channel mean, and channel standard deviation over
  50 outer folds measure tuning stability.
- A 10,000-run paired cluster bootstrap resamples base cases, not queries. It
  reports the tuned-procedure delta against the fixed current triple and the
  strongest tuned pair.

## 5. Deployment decision

Adopt the final all-data three-way candidate only when:

1. it satisfies the exact-title contract;
2. the nested out-of-fold tuned-procedure delta versus current has a positive
   95% cluster-bootstrap lower bound; and
3. the triple is not significantly dominated by the strongest pair.

Otherwise retain 0.40/0.40/0.20. Pair results are diagnostic ablations and
cannot remove a production retrieval path on this construction-aware corpus.
The report must preserve index hashes, fold assignments, every fold-selected
weight, query errors, and the final decision.
