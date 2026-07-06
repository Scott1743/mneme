from pathlib import Path

from okflib import list_concepts, parse_frontmatter, read_concept

SAMPLE = Path(__file__).parent.parent / "sample-bundle"


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
