"""L3 shared tools for mneme Strands agents. Wraps okflib (L1) + indexlib (L2)."""
from __future__ import annotations

import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

from strands import tool


def slug_from_path(path) -> str:
    base = Path(path).stem
    return re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-")


def resolve_bundle(config_path=None):
    if config_path is None:
        config_path = Path.home() / ".config" / "mneme" / "config.toml"
    config_path = Path(config_path)
    if config_path.exists():
        for line in config_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("bundle_path"):
                val = line.split("=", 1)[1].strip().strip('"').strip("'")
                if val:
                    return Path(val)
    env = os.environ.get("MNEME_BUNDLE")
    if env:
        return Path(env)
    import okflib
    cwd = Path.cwd()
    for d in [cwd, *cwd.parents]:
        idx = d / "index.md"
        if idx.exists():
            parsed = okflib.parse_frontmatter(idx.read_text(encoding="utf-8"))
            if parsed and parsed[0].get("okf_version"):
                return d
    wiki = Path.cwd() / "wiki"
    return wiki if wiki.exists() else None


def _bundle() -> Path:
    b = resolve_bundle()
    if b is None:
        raise SystemExit("mneme: no bundle found — run `mneme init <path>` or set ~/.config/mneme/config.toml")
    return b


@tool
def read_source(path: str) -> str:
    """Read a source file (.md/.txt) and return its full text."""
    return Path(path).read_text(encoding="utf-8")


@tool
def list_concepts() -> list:
    """List all concept IDs in the wiki bundle."""
    import okflib
    return okflib.list_concepts(str(_bundle()))


@tool
def read_concept(concept_id: str) -> str:
    """Read a concept page (frontmatter + body) by concept_id."""
    p = _bundle() / f"{concept_id}.md"
    return p.read_text(encoding="utf-8") if p.exists() else ""


@tool
def search_index(query: str, k: int = 5) -> list:
    """Semantic search the wiki index; return top-k chunks with concept_id, title, text."""
    import indexlib
    bundle = _bundle()
    conn = indexlib.open_index(bundle / ".mneme" / "index.db")
    return indexlib.search(conn, query, k, indexlib.default_embed_fn())


@tool
def write_concept(concept_id: str, frontmatter: str, body: str) -> str:
    """Write a concept page. frontmatter is the YAML block (without --- fences)."""
    p = _bundle() / f"{concept_id}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"---\n{frontmatter}\n---\n{body}\n", encoding="utf-8")
    return str(p)


@tool
def update_index_md(entry_markdown: str, section: str = "Concepts") -> str:
    """Append an entry line to a section of the bundle's index.md. entry_markdown is like '* [Title](path) - desc'."""
    p = _bundle() / "index.md"
    text = p.read_text(encoding="utf-8") if p.exists() else f"# {section}\n"
    if f"# {section}" in text:
        text = text.rstrip() + f"\n{entry_markdown}\n"
    else:
        text = text.rstrip() + f"\n# {section}\n{entry_markdown}\n"
    p.write_text(text, encoding="utf-8")
    return str(p)


@tool
def append_log(op: str, title: str, note: str = "") -> str:
    """Append a dated entry to the bundle's log.md."""
    p = _bundle() / "log.md"
    today = date.today().isoformat()
    entry = f"\n## {today} {op} | {title}\n{note}\n" if note else f"\n## {today} {op} | {title}\n"
    p.write_text((p.read_text(encoding="utf-8") if p.exists() else "# Directory Update Log\n") + entry, encoding="utf-8")
    return str(p)


@tool
def validate() -> str:
    """Run the OKF conformance validator on the bundle; return the report text."""
    v = Path(__file__).parent / "validate_okf.py"
    r = subprocess.run([sys.executable, str(v), str(_bundle())], capture_output=True, text=True)
    return r.stdout


@tool
def find_orphans() -> list:
    """Return concept IDs that are not linked from any other concept page."""
    import okflib
    bundle = _bundle()
    ids = set(okflib.list_concepts(str(bundle)))
    linked = set()
    for p in bundle.rglob("*.md"):
        rel = p.relative_to(bundle).as_posix()
        if rel in ("index.md", "log.md"):
            continue
        for m in re.finditer(r"\]\((/[^\)]+\.md)\)", p.read_text(encoding="utf-8")):
            linked.add(m.group(1).lstrip("/")[:-3])
    return sorted(ids - linked)