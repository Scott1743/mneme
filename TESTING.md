# Testing Mneme

Default: `pytest` (no wheel, no PyPI, no extras).

Markers:

- `unit`: fast deterministic.
- `integration`: one bundle, end-to-end.
- `release`: zip/version/release-layout.
- `docs`: documentation assertions.
- `e2e`, `compat`, `network`: skipped by default.

CI matrix: Python 3.11, 3.12, 3.13 only.

Local L0/L1 only; L2 deferred.

## Running the suite

```bash
# All offline tests (default addopts: -m "not network").
pytest

# A specific marker.
pytest -m release

# E2E (may need network for external bundles).
pytest -m e2e
```

## Adding tests

1. Tag every test file with the appropriate `pytestmark = pytest.mark.<LAYER>`
   so the marker table above stays truthful.
2. Mark network-dependent tests with `@pytest.mark.network` so the default
   addopts (`-m "not network"`) keeps the offline suite green.
3. New fixtures live under `tests/fixtures/<area>/`; document them in
   `tests/fixtures/README.md`.
4. Keep the OKF v0.1 contract intact — the test suite is the freeze gate.
