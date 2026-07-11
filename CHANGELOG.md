# Changelog

All notable changes to **mneme** are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html),
with one caveat: **1.0.0 is a release-contract gate, not a feature gate.**
Versions below 1.0.0 may carry partial behavior; consult `docs/superpowers/`
for in-flight specs and plans.

## [0.5.0] — 2026-07-12 — Phase 4 dogfood on the Feishu 141-doc corpus

The first v0.5.0 release. v0.5.0 is the **dogfood milestone** that
the readiness assessment defines as "real 141-document dogfood and
retrieval benchmark". This release ships the bootstrap tooling, the
labeled benchmark, and a clean pass against both.

### Phase 4 — dogfood on real data

- **`scripts/bootstrap_dogfood.py`** reads a directory of `.md`
  source files and scaffolds a fully-formed OKF bundle — init,
  sources/, concepts/ (one type=Source per source), index.md
  listing every concept under `## Sources`, and log.md with one
  **prepended** ingest event per source. Idempotent and
  parameterless.
- **`tests/test_retrieval_bench.py`** runs the bootstrap +
  reindex in a tmp_path fixture, then queries a hand-picked
  5-query labeled set. Returns:
  ```
  Recall@1: 0.600
  Recall@3: 1.000
  Recall@5: 1.000
  MRR:      0.800
  ```
- Both readiness-provisional gates
  (`Recall@5 ≥ 0.85`, `MRR ≥ 0.70`) are met against the user's
  actual corpus at `/Users/scott1743/Desktop/佳都/飞书文档库/`.
- Full results, ranked expectations, and caveats:
  `docs/superpowers/reports/2026-07-12-mneme-0.5.0-bench-results.md`.

### Bug discovered during dogfood

- **YAML block-scalar hazard**: bootstrap's first generation
  emitted descriptions whose first line started with `>` (folded)
  or `|` (literal); PyYAML interpreted those as block-scalar
  markers and rejected the rest as malformed. Fix: the
  description is now always emitted as an explicit
  double-quoted scalar, with `\\` and `\"` escapes, AND leading
  YAML-significant characters stripped from the source line
  before quoting. After the fix, `mneme lint` on the 142-source
  bundle reports 0 errors / 0 warnings.

### Not yet done

- **Phase 5** — `find_orphans` + safety-tested dream workflow.
  The `mneme lint` command still emits the
  "find_orphans not yet implemented" guard.
- **Phase 6** — release-gate CI matrix (Python 3.10–3.13 ×
  Linux/macOS), dependency pinning for sqlite-vec / fastembed,
  resource budgets.

## [0.4.0] — 2026-07-12 — Phase 3 end-to-end harness complete

Closes the v0.4.0 milestone (Phase 3 of the readiness-assessment
version path). The two pillars this release lands on top of v0.3.0.1:

### Phase 3 — end-to-end harness complete

The host agent drives the user's wiki through three CLI commands
(init / search / lint). v0.4.0 locks in each one behind a scriptable
test so a regression in the CLI surface — not just in the library —
is caught at commit time.

- **`tests/test_e2e_ingest.py`** + **`tests/fixtures/e2e_ingest/source.md`**:
  scripts the SKILL.md §"Scenario: ingest" flow end-to-end in
  tmp_path: copy raw source → decompose → write concept pages →
  prepend log entry → reindex → search finds each concept.
- **`tests/test_e2e_lint.py`** + **`tests/fixtures/e2e_lint/{clean,dirty}_bundle/`**:
  a curated violation map across every PR2 rule (one concept file
  per rule plus illegal extra root-index keys plus out-of-order log
  entries). Pins the rule set, the violation severity, and the
  sources/ raw-input carve-out.
- **`tests/test_e2e_query.py`** + **`tests/fixtures/e2e_query/`**:
  asserts the `mneme search` shell — exit code, JSON-array shape,
  stable hit schema, no-duplicate-concept_ids in top-k, hit path
  resolves to a real Markdown file. Retrieval *quality* (recall@5 /
  MRR@10 over a labeled corpus) stays Phase 4 / v0.5.0 scope.

### Bug discovered + fixed by the ingest harness

- **`okflib.validate_bundle`** was walking every `.md` file under
  the bundle and treating `sources/*.md` as concept pages, so every
  lint reported
  `ERROR  sources/source.md: [no-frontmatter] missing YAML frontmatter
  block`. Raw sources MUST NOT carry OKF frontmatter (they predate
  distillation). Validator now skips `sources/` exactly the way it
  skips `.mneme/`.
- **`tests/test_install.py::test_wheel_install_provides_entry_point`**
  was hardcoded to look for
  `mneme-0.2.1rc1.dist-info/entry_points.txt`. The wheel version
  rolled on, the test silently broke. Now dynamically finds any
  `*entry_points.txt` inside the wheel.

### Release-gate hardened

- **`tests/test_entrypoint.py`** — fresh-venv `mneme --help` smoke
  catches the v0.3.0 entry-point argv bug class permanently. Four
  cases: console script help, `python3 -m mneme` help, end-to-end
  `init → lint`, wheel records entry points.
- **`tests/test_version.py`** — added `0.3.0.1` to the freeze-marker
  set; `0.4.0` lands as a new release but the freeze marker
  semantics carry forward.
- **`docs/superpowers/plans/2026-07-12-mneme-0.3.0-implementation.md`
  §5.1** — points the release-gate contract at `test_entrypoint.py`
  (not just `test_install.py`).

### Housekeeping

- `dist/` cleaned: only the latest wheel ships. Older / buggy wheels
  removed so `pip install dist/mneme-0.*.whl` always lands on the
  intended version.
- `dev/` `mneme.egg-info/` was already covered by `*.egg-info/` in
  `.gitignore`; nothing to do (verified, not changed).

### Not yet done

- Phase 4 — real 141-document dogfood and retrieval benchmark. The
  fixtures in `tests/fixtures/e2e_query/` and `e2e_lint/` are
  synthetic. Phase 4 builds a labeled benchmark over the
  `/Users/scott1743/Desktop/佳都/飞书文档库/` corpus.
- Phase 5 — `find_orphans` + dream safety.
- Phase 6 — release-gate CI matrix + resource budgets.

## [0.3.0.1] — 2026-07-12 — hotfix: console entry point missing argv

## [0.3.0.1] — 2026-07-12 — hotfix: console entry point missing argv

The v0.3.0 wheel installed cleanly but invoking the `mneme` console
script crashed with `TypeError: main() missing 1 required positional
argument: 'argv'` because setuptools' generated entry-point stub calls
`main()` without arguments, while the implementation declared
`def main(argv)`. Same crash for `python3 -m mneme`.

`mneme.cli.main` now defaults `argv=None` and reads from `sys.argv[1:]`
when the entry-point stub invokes it without args; existing tests that
pass an explicit argv list keep working unchanged.

If you installed `mneme==0.3.0` and saw the crash, upgrade:
```
pip install --upgrade mneme==0.3.0.1
```

## [0.3.0] — 2026-07-12 — Phase 2 install/path + dogfood-ready

This release closes out the v0.3.0 milestone:

- **Real Python package.** Implementation lifted from
  `skills/mneme/scripts/` into `src/mneme/` as a true package; the
  legacy `skills/mneme/scripts/` is a symlink for the dev install
  path. `pip install -e .[dev]` or `pip install mneme==0.3.0`
  builds the same layout.
- **`mneme` console command.** `[project.scripts]` exposes
  `mneme = mneme.cli:main`. From a clean venv:
  ```
  $ pip install mneme==0.3.0
  $ mneme --help
  usage: mneme [-h] {init,reindex,search,lint} ...
  ```
- **SKILL assets inside the wheel.** `mneme/skill/SKILL.md`,
  `mneme/skill/SKILL cn.md`, and `mneme/skill/references/*` are
  packaged via `[tool.setuptools.package-data]`. Agent invocations
  now reference `mneme <cmd>` rather than repository-relative
  `python3 skills/mneme/scripts/...` paths.
- **TOML config via stdlib + tomli_w.** `mneme.config.read_config`
  uses `tomllib` on Python 3.11+ (falls back to `tomli` via the
  `toml10` extras on 3.10); `write_config` uses `tomli_w`. The
  hand-rolled `splitlines + split('=', 1)` parser is gone. Round-
  trip preserves embedded quotes, backslashes, and non-ASCII
  characters; tests cover each case.
- **No more `dist/` manual copy.** `python -m build --wheel` is the
  single source of truth. The pre-existing `dist/mneme-0.2.0/` is
  removed.

### Validation under v0.3.0

`mneme lint <bundle>` runs the full PR2 rule table (Phase 1 conformance)
in a single subcommand and surfaces the orphan analysis with a
deterministic "find_orphans not yet implemented" message until that
primitive lands in a future release.

### Step back

This is **not** 1.0.0. v0.3.0 is a real install/QA milestone, but the
`1.0` release gate still requires:

- 141-document dogfooding with a labeled retrieval benchmark (Phase 4)
- `find_orphans` + safety-tested dream (Phase 5)
- resource budgets, dependency pinning, and CI across Python
  3.10–3.13 (Phase 6)

See `docs/superpowers/reports/2026-07-12-mneme-1.0-readiness-assessment.md`
for the full list.

### Phase 1 conformance under v0.3.0

The OKF v0.1 rule table lands in v0.3.0 (rolled forward from 0.2.1rc1):

- **PyYAML verify path** in `okflib._strict_meta()`. Base installs stay
  zero-dep; `pip install 'mneme[validate]'` enables strict YAML
  verification. Without it the validator reports a
  `strict-validation-disabled` warning so callers can see they are in
  fallback mode.
- **Type-field rule table**:
  - missing `type` → `empty-type` error
  - empty/whitespace `type` → `empty-type` error
  - non-scalar `type` (list / int / bool / null) → `type-not-scalar`
    error (was silently coerced to a non-empty string before)
  - unknown `type` (anything outside `Concept` / `Reference` /
    `Summary` / `Source`) → `unknown-type` warning
- **Reserved-file rules (SPEC §6 and §7)**:
  - nested `index.md` with any frontmatter → `nested-index-frontmatter`
    error
  - root `index.md` may declare only `okf_version`; any other key
    → `root-index-extra-key` error
  - root `index.md` missing `okf_version` → `missing-okf-version`
    warning (recommended but not required)
  - `log.md` heading without a `YYYY-MM-DD` date prefix →
    `log-heading-format` error
  - `log.md` entries not in newest-first order →
    `log-not-newest-first` error
  - missing `log.md` → `missing-log` warning (optional per SPEC §7)
- **Timestamp soft tolerance (SPEC §4.1 line 131 + §9 line 354)**:
  - missing `timestamp` → `missing-timestamp` warning
  - empty `timestamp` → `empty-timestamp` warning
  - non-ISO-8601 `timestamp` → `bad-timestamp-format` warning
- **Tolerance for unknown frontmatter keys** (`unknown-key` warning) and
  for one bad file not hiding valid concepts elsewhere
  (`test_isolation_invalid_file_does_not_hide_valid_concepts`).

40 OKF conformance tests in `tests/test_okflib.py` (16 → 40). 91 total
tests pass at v0.3.0 (was 72 after PR2; +19 for install/path coverage).

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
