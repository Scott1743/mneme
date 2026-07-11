import subprocess
import sys
from pathlib import Path

from mneme.okflib import list_concepts, parse_frontmatter, read_concept, validate_bundle

SAMPLE = Path(__file__).parent.parent / "sample-bundle"
FIX = Path(__file__).parent / "fixtures"
VALIDATOR = Path(__file__).parent.parent / "src" / "mneme" / "validate_okf.py"


def test_parse_frontmatter_basic():
    text = "---\ntype: Concept\ntitle: Foo\ntags: [a, b]\n---\n# Body\n"
    meta, body = parse_frontmatter(text)
    assert meta["type"] == "Concept"
    assert meta["title"] == "Foo"
    assert meta["tags"] == ["a", "b"]
    assert body.startswith("# Body")


def test_parse_frontmatter_quoted():
    text = "---\ntype: \"Reference\"\ntitle: 'Has, comma'\n---\nbody\n"
    meta, _ = parse_frontmatter(text)
    assert meta["type"] == "Reference"
    assert meta["title"] == "Has, comma"


def test_parse_frontmatter_none_when_absent():
    assert parse_frontmatter("# just a body\nno frontmatter\n") is None


def test_list_concepts_excludes_reserved():
    ids = list_concepts(SAMPLE)
    assert "concepts/llm-wiki" in ids
    assert "concepts/okf" in ids
    assert "index" not in ids
    assert "log" not in ids


def test_read_concept_returns_metadata_and_body():
    meta, body = read_concept(SAMPLE, "concepts/okf")
    assert meta["type"] == "Reference"
    assert "OKF" in body


def test_read_concept_missing_returns_none():
    assert read_concept(SAMPLE, "concepts/nope") is None


def test_valid_bundle_passes():
    report = validate_bundle(SAMPLE)
    assert report.ok, [(v.path, v.rule, v.detail) for v in report.errors]


def test_missing_frontmatter_fails():
    report = validate_bundle(FIX / "missing_frontmatter")
    assert not report.ok
    assert any(v.rule == "no-frontmatter" for v in report.errors)


def test_empty_type_fails():
    report = validate_bundle(FIX / "empty_type")
    assert not report.ok
    assert any(v.rule == "empty-type" for v in report.errors)


def test_unknown_type_passes():
    report = validate_bundle(FIX / "unknown_type")
    assert report.ok


def test_extra_keys_pass():
    report = validate_bundle(FIX / "extra_keys")
    assert report.ok


def test_broken_link_is_warning_not_error():
    report = validate_bundle(FIX / "broken_link")
    assert report.ok  # broken link is a warning, not an error (OKF §9 tolerance)
    assert any(v.rule == "broken-link" for v in report.warnings)


def _run(bundle):
    return subprocess.run([sys.executable, str(VALIDATOR), str(bundle)], capture_output=True, text=True)


def test_cli_valid_bundle_exit_zero():
    r = _run(SAMPLE)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "0 error(s)" in r.stdout


def test_cli_invalid_bundle_exit_one():
    r = _run(FIX / "missing_frontmatter")
    assert r.returncode == 1
    assert "no-frontmatter" in r.stdout


def test_list_concepts_skips_mneme_dir(tmp_path):
    import os
    bundle = tmp_path / "b"
    (bundle / "concepts").mkdir(parents=True)
    (bundle / "concepts" / "ok.md").write_text("---\ntype: Concept\n---\nbody\n")
    (bundle / ".mneme").mkdir()
    (bundle / ".mneme" / "index.db").write_text("not md")
    ids = list_concepts(bundle)
    assert "concepts/ok" in ids
    assert not any(".mneme" in i for i in ids)


# ─────────────────────────────────────────────────────────────────────────────
# PR2 §4 — OKF v0.1 conformance red tests (Phase 1 freeze prerequisite).
# Each test fails on the current hand-rolled validator. PR2-1 (PyYAML
# verify-path refactor) + PR2-2 (rule table) turn them green.
# ─────────────────────────────────────────────────────────────────────────────

import pytest


def _errors(report):
    return [(v.path, v.rule) for v in report.errors]


def _warnings(report):
    return [(v.path, v.rule) for v in report.warnings]


# §4.1 — YAML parse failures: must reject when PyYAML is available.
@pytest.mark.parametrize(
    "fixture_name",
    [
        "unterminated_flow",
        "unclosed_quote",
        "bad_indent",
    ],
)
def test_yaml_malformed_rejected_when_yaml_available(fixture_name):
    """§4.1: the validator must reject YAML that PyYAML rejects. The
    hand-rolled parser at okflib.parse_frontmatter accepts all three of
    these as malformed-but-recoverable. With PyYAML installed, this test
    passes; without it, the importorskip line below marks the test as
    skipped so we don't claim coverage we can't exercise.
    """
    pytest.importorskip("yaml")
    d = FIX / "yaml_malformed"
    report = validate_bundle(d)
    # Each parametrized case targets a specific file inside the fixture;
    # `validate_bundle(d)` walks files directly under d, so `rel` is the
    # basename only — match on rule + filename.
    yaml_errors = [
        e for e in _errors(report)
        if e[1] == "malformed-yaml" and f"{fixture_name}.md" in e[0]
    ]
    assert yaml_errors, (
        f"validate_bundle did not flag malformed YAML in {fixture_name}.md: "
        f"got {_errors(report)}"
    )


def _strip_frontmatter(text):
    import re
    m = re.match(r"\A---[ \t]*\n(.*?)\n---[ \t]*\n?", text, re.S)
    return m.group(1) if m else text


def test_yaml_multiline_block_scalar_ok():
    """§4.1: multi-line block scalar (`|` / `>`) is valid YAML. Validates
    cleanly, no malformed-yaml error.
    """
    d = FIX / "yaml_malformed"
    report = validate_bundle(d)
    # Only the multiline file should pass; the others error in PyYAML mode.
    # We isolate by checking that multiline_ok.md did not produce a
    # malformed-yaml error.
    ml_err = [
        e for e in _errors(report)
        if "multiline_ok.md" in e[0] and e[1] == "malformed-yaml"
    ]
    assert not ml_err, (
        f"validate_bundle flagged multiline_ok.md as malformed YAML: {ml_err}"
    )


# §4.2 — type field checks
def test_type_whitespace_only_fails():
    report = validate_bundle(FIX / "type_whitespace")
    assert not report.ok
    assert any(v.rule == "empty-type" for v in report.errors)


@pytest.mark.parametrize(
    "subfile",
    ["int", "bool", "null"],
)
def test_type_non_string_fails(subfile):
    """§4.2: type must be a non-empty string. int/bool/null all fail."""
    d = FIX / "type_non_string"
    report = validate_bundle(d)
    assert not report.ok
    bad = [
        e for e in _errors(report)
        if f"{subfile}.md" in e[0] and e[1] in ("empty-type", "type-not-scalar")
    ]
    assert bad, (
        f"validate_bundle did not reject non-string type in {subfile}.md "
        f"({_errors(report)})"
    )


def test_type_list_rejected():
    """§4.2: OKF §4.1 mandates type as <Type name> (scalar). Lists must be
    rejected, not silently coerced to a string by the hand parser.
    """
    report = validate_bundle(FIX / "type_as_list")
    assert not report.ok
    assert any(
        v.rule in ("empty-type", "type-not-scalar") for v in report.errors
    ), f"got {_errors(report)}"


# §4.3 — unknown type / extra keys warn only
def test_unknown_type_warns_only():
    """§4.3: the type vocab is not centralized; unknown type values
    produce a warning, not an error (OKF §9 tolerance).
    """
    report = validate_bundle(FIX / "unknown_type")
    assert report.ok
    assert any(
        v.rule == "unknown-type" for v in report.warnings
    ), f"got warnings={_warnings(report)}"


def test_extra_frontmatter_keys_warn_only():
    report = validate_bundle(FIX / "extra_keys")
    assert report.ok
    assert any(
        v.rule == "unknown-key" for v in report.warnings
    ), f"got warnings={_warnings(report)}"


# §4.4 — nested index frontmatter is an error
def test_nested_index_with_frontmatter_rejected():
    d = FIX / "nested_index_with_fm"
    report = validate_bundle(d)
    assert not report.ok
    assert any(
        v.rule == "nested-index-frontmatter"
        for v in report.errors
    ), f"got errors={_errors(report)}"


# §4.5 — root index key whitelist
def test_root_index_extra_keys_rejected():
    """§4.5: root index.md may declare okf_version only; any other
    frontmatter key is an error."""
    d = FIX / "root_index_extra"
    report = validate_bundle(d)
    assert not report.ok
    assert any(
        v.rule == "root-index-extra-key" for v in report.errors
    ), f"got errors={_errors(report)}"


def test_root_index_missing_okf_version_warns_only():
    d = FIX / "root_index_no_okf_version"
    report = validate_bundle(d)
    assert report.ok
    assert any(
        v.rule == "missing-okf-version" for v in report.warnings
    ), f"got warnings={_warnings(report)}"


# §4.6 — log.md format + ordering
def test_log_heading_format_enforced():
    d = FIX / "log_bad_format"
    report = validate_bundle(d)
    assert not report.ok
    assert any(
        v.rule == "log-heading-format" for v in report.errors
    ), f"got errors={_errors(report)}"


def test_log_newest_first_enforced():
    d = FIX / "log_out_of_order"
    report = validate_bundle(d)
    assert not report.ok
    assert any(
        v.rule == "log-not-newest-first" for v in report.errors
    ), f"got errors={_errors(report)}"


def test_log_missing_warns_only(tmp_path):
    bundle = tmp_path / "b"
    bundle.mkdir()
    (bundle / "index.md").write_text(
        '---\nokf_version: "0.1"\n---\n# Concepts\n', encoding="utf-8"
    )
    report = validate_bundle(bundle)
    assert report.ok
    assert any(
        v.rule == "missing-log" for v in report.warnings
    ), f"got warnings={_warnings(report)}"


# §4.8 — isolation
def test_isolation_invalid_file_does_not_hide_valid_concepts(tmp_path):
    """§4.8: one invalid concept must not erase the validator's view of
    the rest of the bundle.
    """
    bundle = tmp_path / "b"
    bundle.mkdir()
    (bundle / "index.md").write_text(
        '---\nokf_version: "0.1"\n---\n# Concepts\n', encoding="utf-8"
    )
    (bundle / "concepts").mkdir()
    (bundle / "concepts" / "good.md").write_text(
        "---\ntype: Concept\ntitle: Good\n---\n# ok\n", encoding="utf-8"
    )
    (bundle / "concepts" / "bad.md").write_text(
        "---\ntype: [malformed]\ntitle: Bad\n---\n# broken\n",
        encoding="utf-8",
    )
    report = validate_bundle(bundle)
    # At least one error must mention bad.md; good.md must remain readable.
    assert any(
        "concepts/bad.md" in v.path for v in report.errors
    ), f"got errors={_errors(report)}"
    meta, body = read_concept(bundle, "concepts/good")
    assert meta["type"] == "Concept"
    assert body.startswith("# ok")


# §4.9 — fallback
def test_validate_reserved_empty_body_warns(tmp_path):
    """Empty index.md body is a warning, not an error."""
    bundle = tmp_path / "b"
    bundle.mkdir()
    (bundle / "index.md").write_text("", encoding="utf-8")
    report = validate_bundle(bundle)
    assert report.ok
    assert any(
        v.rule == "bad-reserved-index" for v in report.warnings
    ), f"got warnings={_warnings(report)}"


def test_type_case_preserved(tmp_path):
    """The validator does not normalize type case. 'concept' (lowercase)
    is treated as a valid (but unknown) type — warning only."""
    bundle = tmp_path / "b"
    bundle.mkdir()
    (bundle / "index.md").write_text(
        '---\nokf_version: "0.1"\n---\n# Concepts\n', encoding="utf-8"
    )
    (bundle / "concepts").mkdir()
    (bundle / "concepts" / "x.md").write_text(
        "---\ntype: concept\ntitle: Lower\n---\nbody\n", encoding="utf-8"
    )
    report = validate_bundle(bundle)
    assert report.ok
    assert any(
        v.rule == "unknown-type" for v in report.warnings
    ), f"got warnings={_warnings(report)}"


# §4.10 — timestamp soft tolerance (OKF §4.1 line 131 + §9 line 354)
def test_missing_timestamp_warns_only(tmp_path):
    bundle = tmp_path / "b"
    bundle.mkdir()
    (bundle / "index.md").write_text(
        '---\nokf_version: "0.1"\n---\n# Concepts\n', encoding="utf-8"
    )
    (bundle / "concepts").mkdir()
    (bundle / "concepts" / "x.md").write_text(
        "---\ntype: Concept\ntitle: No timestamp\n---\nbody\n",
        encoding="utf-8",
    )
    report = validate_bundle(bundle)
    assert report.ok
    assert any(
        v.rule == "missing-timestamp" for v in report.warnings
    ), f"got warnings={_warnings(report)}"


def test_empty_timestamp_warns_only(tmp_path):
    bundle = tmp_path / "b"
    bundle.mkdir()
    (bundle / "index.md").write_text(
        '---\nokf_version: "0.1"\n---\n# Concepts\n', encoding="utf-8"
    )
    (bundle / "concepts").mkdir()
    (bundle / "concepts" / "x.md").write_text(
        '---\ntype: Concept\ntitle: Empty\ntimestamp: ""\n---\nbody\n',
        encoding="utf-8",
    )
    report = validate_bundle(bundle)
    assert report.ok
    assert any(
        v.rule == "empty-timestamp" for v in report.warnings
    ), f"got warnings={_warnings(report)}"


def test_bad_format_timestamp_warns_only(tmp_path):
    bundle = tmp_path / "b"
    bundle.mkdir()
    (bundle / "index.md").write_text(
        '---\nokf_version: "0.1"\n---\n# Concepts\n', encoding="utf-8"
    )
    (bundle / "concepts").mkdir()
    (bundle / "concepts" / "x.md").write_text(
        "---\ntype: Concept\ntitle: Bad date\ntimestamp: yesterday\n---\nbody\n",
        encoding="utf-8",
    )
    report = validate_bundle(bundle)
    assert report.ok
    assert any(
        v.rule == "bad-timestamp-format" for v in report.warnings
    ), f"got warnings={_warnings(report)}"
