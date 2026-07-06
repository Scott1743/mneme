from okflib import parse_frontmatter


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
