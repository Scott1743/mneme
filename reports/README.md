# Retrieval Research Reports

`designs/` contains preregistered experiment designs. `experiments/` contains
completed, self-contained HTML reports and their linked result artefacts.

The first design establishes how Mneme 0.5, 2.2, and the future 3.2 hybrid
retrieval path will be compared on one frozen corpus. It is informed by
`.research/rag-sota-2026.md`; it is a local-system protocol, not a claim on
BEIR, MTEB, or CMTEB leaderboards.

## Completed experiments

- [`2026-07-15 Design 01 历史回归`](experiments/2026-07-15-design01-historical.html)：
  在同一份完整冻结语料上执行 L1（FTS5）、L2（BGE 语义检索）与 L1+L2（RRF）的
  5 条历史 qrels 回归，报告为中文，并附 manifest 与逐条 JSONL 审计结果。它是
  可复跑的历史子集，不替代设计要求的 80 条双人标注主分析。

- [`2026-07-15 L1 pilot`](experiments/2026-07-15-l1-pilot.html): a reproducible
  FTS5-only replay of the five historical qrels against the available private
  142-document corpus. Its manifest and JSONL results sit beside the report.
  It is explicitly not the Design 01 primary comparison: it has no 80-query
  independently annotated qrels, dense/hybrid stage, or reranker.
