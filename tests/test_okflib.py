from pathlib import Path

from okflib import list_concepts, parse_frontmatter, read_concept, validate_bundle

SAMPLE = Path(__file__).parent.parent / "sample-bundle"
FIX = Path(__file__).parent / "fixtures"


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
