# Retrieval Research Reports

`designs/` contains the frozen protocol. `experiments/` contains the current
self-contained report and its JSONL/manifest audit artefacts. Historical
five-query reports were removed because they contained an incorrect qrel and
were not suitable for primary conclusions.

Current protocols:

- [Graph Enrichment Retrieval Benchmark](designs/2026-07-21-graph-enrichment-benchmark.md)
  measures the incremental value of approved Graph enrichment.
- [Hybrid Weight Comparison and Ablation](designs/2026-07-23-hybrid-weight-ablation.md)
  uses the active local Graph/FTS5/L2 environment, synthetic robustness
  variants, validation-only tuning, and a held-out decision rule. It is the
  pilot retained for audit history.
- [Hybrid Weight Nested Cross-Validation](designs/2026-07-23-hybrid-weight-nested-cv.md)
  supersedes the pilot for deployment decisions with a 1% exhaustive grid,
  repeated grouped outer folds, and base-case cluster bootstrap.

Both are construction-aware diagnostics, not claims on BEIR, MTEB, CMTEB, or
general semantic-search quality.
