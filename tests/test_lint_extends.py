"""Task 5 — lint extends validate_bundle (no reinvention).

`okflib.lint_bundle` is the thin wrapper that reuses `validate_bundle`'s
existing OKF v0.1 diagnostics and adds the Mneme writer rule: every
Mneme-written concept page must carry ≥1 `tags` value. The wrapper does
not rewrite any OKF logic; it only translates the base `Report` into
flat diagnostics and appends `MNEME-TAG-MISSING` for pages missing tags.

Severity contract (per SKILL.md "tags is a writer rule, not a protocol
rule" + OKF §9 tolerance):
  * `okf_external=False` → MNEME-TAG-MISSING is **ERROR** (this is a
    Mneme-authored bundle; tags are mandatory for cross-page navigation).
  * `okf_external=True`  → MNEME-TAG-MISSING is **WARN** (the bundle
    was produced by an external OKF consumer; we tolerate it).

The base OKF validator already enforces §9 isolation (one bad file
must not hide others), so `lint_bundle` preserves that property by
appending diagnostics per-file rather than short-circuiting.
"""
from __future__ import annotations

from pathlib import Path

from mneme import okflib


def _seed_bundle(b: Path, *, with_untagged: bool = False) -> Path:
    """Build a minimal OKF bundle: one tagged concept, optional untagged.

    The fixture deliberately avoids frontmatter defects that would
    trip OKF's own diagnostics — the only signal we want to assert
    on is the tag policy itself.
    """
    (b / "concepts").mkdir(parents=True, exist_ok=True)
    (b / "concepts" / "a.md").write_text(
        "---\n"
        "type: Concept\n"
        "title: A\n"
        "description: alpha\n"
        "tags: [a]\n"
        "timestamp: 2026-07-13T00:00:00Z\n"
        "---\n"
        "body\n"
    )
    if with_untagged:
        (b / "concepts" / "b.md").write_text(
            "---\n"
            "type: Concept\n"
            "title: B\n"
            "description: beta\n"
            "timestamp: 2026-07-13T00:00:00Z\n"
            "---\n"
            "body\n"
        )
    (b / "index.md").write_text("# Index\n")
    return b


def test_lint_passes_clean_bundle(tmp_path):
    """Clean tagged bundle: no ERROR diagnostics from OKF or Mneme rules."""
    b = _seed_bundle(tmp_path)
    report = okflib.lint_bundle(b, require_tags=True)
    assert not [d for d in report["diagnostics"] if d["severity"] == "ERROR"], (
        f"clean bundle raised ERROR diagnostics: "
        f"{[d for d in report['diagnostics'] if d['severity'] == 'ERROR']}"
    )


def test_lint_flags_missing_tags_on_mneme_written_page(tmp_path):
    """Mneme-written bundle (okf_external=False): missing tags = ERROR."""
    b = _seed_bundle(tmp_path, with_untagged=True)
    report = okflib.lint_bundle(b, require_tags=True, okf_external=False)
    codes = {d["code"] for d in report["diagnostics"]}
    assert "MNEME-TAG-MISSING" in codes, (
        f"expected MNEME-TAG-MISSING; got codes={codes}; "
        f"diagnostics={report['diagnostics']}"
    )
    sev = {
        d["code"]: d["severity"]
        for d in report["diagnostics"]
        if d["code"] == "MNEME-TAG-MISSING"
    }
    assert sev["MNEME-TAG-MISSING"] == "ERROR"


def test_lint_demotes_missing_tags_for_external_okf(tmp_path):
    """External OKF bundle (okf_external=True): missing tags = WARN only.

    This honors OKF §9 tolerance: consumers must not reject a bundle
    because of optional field absence. `tags` is *recommended* by OKF
    §4.1, so a non-Mneme bundle without tags is tolerated.
    """
    b = _seed_bundle(tmp_path, with_untagged=True)
    report = okflib.lint_bundle(b, require_tags=True, okf_external=True)
    sev = {d["code"]: d["severity"] for d in report["diagnostics"]}
    assert sev.get("MNEME-TAG-MISSING") == "WARN", (
        f"external OKF should demote MNEME-TAG-MISSING to WARN; "
        f"got sev={sev}"
    )


def test_lint_does_not_reintroduce_validate_bundle_logic():
    """`lint_bundle` must call validate_bundle; not reimplement OKF rules.

    This is a structural guard: it pins the "no reinvention" hard rule
    from Task 5. If a future refactor duplicates OKF logic into
    `lint_bundle`, this test fires.
    """
    import inspect

    src = inspect.getsource(okflib.lint_bundle)
    assert "validate_bundle" in src, (
        "lint_bundle must delegate to validate_bundle; "
        "do not reimplement OKF §3-§9 validation in the wrapper."
    )