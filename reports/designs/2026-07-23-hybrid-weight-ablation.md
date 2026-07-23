# Hybrid Weight Comparison and Ablation

> **Status**: superseded pilot · 2026-07-23
> **Purpose**: choose Graph/FTS5/L2 fusion weights from the active local Mneme
> environment instead of assigning them by intuition.

## 1. Research questions

1. Which individual retrieval leg is strongest for exact, expanded, sentence,
   typo, and omission queries derived from approved enriched Graph nodes?
2. Does every second and third leg add held-out ranking value?
3. Which page-level reciprocal-rank fusion weights maximize robust held-out
   ranking quality on the current bundle?

This is a construction-aware diagnostic benchmark. The enriched extraction
manifest supplies both query vocabulary and page relevance labels, so the
result is valid for tuning this bundle but is not a general retrieval claim.

## 2. Corpus and query construction

The runner resolves the configured bundle and requires fresh `graph.db`,
`fts.db`, `l2.db`, and `graph-extractions.json`. It never writes the bundle.

Eligible enriched entities have confidence >= 0.80, a 2-42 character name,
and at least one source page. Entities are aggregated case-insensitively, and
all mentioning pages become relevance labels. Up to three stable entity pairs
per source page are added; their labels are pages mentioning both entities.
The title of every enrichment source page is also a base case with that one
page as its relevance label. These title controls prevent a construction-only
Graph benchmark from sacrificing the basic exact-page-title workflow.
All exact-title controls are evaluated together as a deterministic product
contract during weight selection; their longer and noisy variants retain the
grouped validation/holdout assignment used by the statistical benchmark.

Every atomic, pair, or title base case produces five variants:

- `exact`: entity name or two names;
- `long_phrase`: names plus available enriched descriptions;
- `sentence`: a natural-language request containing the names;
- `typo`: a deterministic Chinese confusion substitution, with adjacent
  transposition as fallback;
- `omission`: one character removed from an entity name.

All variants of one base case stay in the same split. A SHA-256 seeded split
assigns 60% of base cases to validation and 40% to holdout. Validation chooses
weights. Holdout is read only after selection and supplies the final claim.

## 3. Systems and weight search

The three legs run once per query with a page pool of 100. Their outputs are
cached, then fused offline with the production scoring contract:

- Graph: normalized reachability score;
- FTS5: reciprocal page rank;
- L2: reciprocal page rank after the production 0.90 distance gate;
- missing legs: weight renormalized across legs returning candidates.

The grid uses 0.05 increments. Pair systems search all positive two-leg
mixtures; the full system searches all mixtures where each leg is at least
0.05. Selection first maximizes all-source-page exact-title Hit@1 as a hard safety guardrail,
then uses validation family-macro MRR@10, worst-family MRR@10, Recall@3, and
proximity to equal weighting. The tested stages are the three individual legs,
three tuned pairs, equal triple, current `0.4/0.4/0.2`, and
validation-tuned triple.

## 4. Metrics

- **Family-macro MRR@10** is primary so the five variants have equal influence.
- **Exact-title Hit@1** is a hard guardrail: a tuned mix must not move a direct
  page-title query below a less relevant neighbor.
- **Worst-family MRR@10** is the robustness guardrail.
- **Hit@1**, **Recall@3**, and **Recall@10** expose reading cost and coverage.
- Clean (`exact`, `long_phrase`, `sentence`) and noisy (`typo`, `omission`)
  slices quantify degradation.
- A fixed-seed query bootstrap reports 95% intervals for holdout MRR and the
  paired tuned-minus-current delta.

## 5. Decision rule and limitations

The product definition of full Hybrid retains all three independently useful
retrieval paths. Adopt the validation-tuned triple only when it preserves the
current mix's holdout exact-title Hit@1, its paired bootstrap MRR improvement
over the current mix has a positive 95% lower bound, and its paired interval
against the strongest tuned pair includes zero. Otherwise retain the current
mix. Pair systems are ablations, not deployment candidates: this
construction-aware query source structurally favors Graph and does not cover
independent lexical searches well enough to justify deleting a retrieval leg.

The report must disclose corpus page count, eligible nodes, split sizes,
dependency/model versions, index hashes, query errors, and the small,
construction-aware nature of the benchmark. Re-running after material Graph
enrichment or corpus growth is required before treating the weights as stable.
