# Changelog

All notable changes to **mneme** are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html),
with one caveat: **1.0.0 is a release-contract gate, not a feature gate.**
Versions below 1.0.0 may carry partial behavior; consult `docs/superpowers/`
for in-flight specs and plans.

## [0.2.1rc1] — 2026-07-12 — freeze dangerous behavior

This is a **freeze pre-release**, not a feature release. It explicitly
removes or guards every behavior flagged P0/P1 in the v0.2.0 readiness
assessment at `docs/superpowers/reports/2026-07-12-mneme-1.0-readiness-assessment.md`.
The version is bumped from `0.2.0` → `0.2.1rc1` so accidental `pip
install mneme` does not pick up dangerous code paths by default.

### Removed (gone, see notes for re-introduction)

- **`mneme dream` scenario and prose-defined auto-curation pipeline.**
  The dream workflow described in v0.2.0's SKILL.md used a similarity
  threshold that did not match sqlite-vec's actual distance metric,
  called a non-existent `okflib.find_orphans()` primitive, and ran
  `git add -A` before resolving the bundle — any of which is a
  merge-blocking defect on its own. The scenario is removed from both
  English and Chinese SKILL.md; a note replaces it citing the
  recovery prerequisites.

### Now explicit and deterministic

- **`mneme lint <bundle>` is now a real subcommand.** Previously
  undocumented in the CLI dispatcher, the command now delegates to
  `validate_okf.py` and emits a deterministic "find_orphans not yet
  implemented" message instead of an opaque `AttributeError`. Exit
  code 3 distinguishes guard-fired from argparse's exit code 2.
- **Ingest scenario redirects the host agent to copy the raw source**
  into `<bundle>/sources/<basename>` **before** distillation, matching
  the OKF v0.1 immutable-source contract.
- **Ingest scenario prepends the new `log.md` entry at the top**, not
  appends. OKF §6 requires newest-first; appending for months produces
  an oldest-first log.
- **`SKILL.md` no longer mentions a fake-embed production fallback.**
  v0.2.0's English SKILL left a "Only acceptable for tests" escape
  hatch; both language variants now tell the host agent to surface
  the model load failure and require `pip install 'mneme[index]'`.

### Documentation cleanup

- **`CLAUDE.md` no longer references the v2.1-deleted Strands agent
  layer.** The "L3 Strands agent (ingest/query/lint)" bullet is gone;
  the directory tree no longer lists `tools.py`/`ingest.py`/`query.py`/
  `lint.py` (none of which exist after the v2.1 thin-CLI refactor);
  the CLI is correctly described as argparse, not "Click 风格".
- **`AGENTS.md` is unchanged.** It already reflects the v2.1+ reality.

### Not yet addressed (deferred per scope, tracked in `docs/superpowers/`)

- Phase 1 OKF conformance TDD — covered by
  `docs/superpowers/plans/2026-07-12-mneme-0.3.0-implementation.md` §4.
- Phase 2 install/path TDD (proper `mneme` wheel) — same plan, §5.
- Real 141-document dogfood and retrieval benchmark — 0.5.0.
- Re-introduction of dream — only after Phase 5 retrieval benchmark
  passes, `find_orphans` + similarity-safe workflow under test, and
  dry-run preview mode + a dedicated safety TDD suite.

## [0.2.0] — 2026-07-11 — search CLI

Added `mneme search <query>` (KNN over the L2 sqlite-vec index), atomic
reindex, BGE/small/zh-v1.5 default model, deterministic test fakes.

## [0.1.x and earlier]

See `git log` for v2.1, v2, v1 and prior history. The skill-first
install path is documented at the project README.
