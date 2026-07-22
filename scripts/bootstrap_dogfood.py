"""Bootstrap a real OKF bundle from a directory of `.md` source files.

Used by Phase 4 (v0.5.0 dogfood). The skills' LLM-driven ingest path
is what we test against; this script performs the same steps
deterministically — one concept page per source — so a CI machine
without an LLM can still stand up a 142-concept bundle for
retrieval benchmarking.

The mapping:

  1. run `mneme init <bundle> --config <cfg>` to scaffold
  2. copy each `<src>/foo.md` unchanged into
     `<bundle>/raw-sources/foo.md.raw`
  3. for each source, write one OKF Source page under
     `<bundle>/sources/<slug>.md` with frontmatter
     `type: Source / title / description / tags / timestamp / resource`
     and body = the source's full text
  4. extend `<bundle>/index.md` so each concept has a `## Sources`
     bullet
  5. **prepend** (not append) a per-source entry to
     `<bundle>/log.md`

After this script returns, the bundle's:

  - raw-sources/  — every original `.md` as byte-identical `.md.raw`
  - sources/      — one OKF provenance page per source, type=Source
  - index.md      — root with okf_version, plus a single ## Sources
                    section listing every concept
  - log.md        — one entry per source, **newest-first**

This script is idempotent: running it twice yields the same bundle.
Re-running overwrites writes from the same run (so the user can
regenerate the dogfood bundle any time).
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Match leading numeric prefixes used by Feishu exports:
#   `001_foo.md`, `12_bar.md`, etc. Strip the prefix + the
#   trailing `.md` to derive the slug.
_SLUG_RE = re.compile(r"^(\d+_)?(.+?)(\.md)?$")


def _slug_for(filename: str) -> str:
    m = _SLUG_RE.match(filename)
    if not m:
        return filename.rsplit(".", 1)[0]
    return m.group(2)


def _source_records(sources: list[Path]) -> list[tuple[Path, str]]:
    """Assign a stable, collision-free concept slug to every source file.

    Feishu exports can contain both ``NNN_<id>.md`` and ``<id>.md``.
    Both normalize to the same historic concept slug, so preserve the first
    one and suffix later occurrences rather than silently overwriting a
    concept page.
    """
    used: set[str] = set()
    records: list[tuple[Path, str]] = []
    for source in sources:
        base = _slug_for(source.name)
        slug = base
        occurrence = 2
        while slug in used:
            slug = f"{base}--{occurrence}"
            occurrence += 1
        used.add(slug)
        records.append((source, slug))
    return records


def _description_for(source_text: str, fallback: str, limit: int = 120) -> str:
    """First non-empty, non-heading line of the source as the description.

    Falls back to the original filename when the source is short on
    prose. Strips leading YAML-significant characters (`>`, `|`, `&`,
    `!`, `*`, `[`, `{`, `'`, `"`) so the description can be emitted
    as a plain scalar without quoting gymnastics.
    """
    for line in source_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        if len(stripped) < limit:
            return stripped.lstrip(">|&!*['\"{- ")
        return stripped[: limit - 3].rstrip().lstrip(">|&!*['\"{- ") + "..."
    return fallback


def bootstrap(corpus: Path, bundle: Path, cfg: Path) -> None:
    corpus = corpus.resolve()
    bundle = bundle.resolve()
    cfg = cfg.resolve()
    bundle.parent.mkdir(parents=True, exist_ok=True)

    if not corpus.is_dir():
        raise SystemExit(f"corpus not a directory: {corpus}")
    sources = sorted(p for p in corpus.glob("*.md") if p.is_file())
    if not sources:
        raise SystemExit(f"no .md files under {corpus}")

    records = _source_records(sources)

    # Step 1: scaffold the bundle.
    if (bundle / "index.md").exists() and (bundle / "log.md").exists():
        print(f"bundle already initialized at {bundle}; reusing")
    else:
        print(f"initializing {bundle}")
        rc = subprocess.run(
            [sys.executable, "-m", "mneme", "init", str(bundle),
             "--config", str(cfg)],
            check=True, capture_output=True, text=True,
        )

    sources_dir = bundle / "sources"
    sources_dir.mkdir(exist_ok=True)
    raw_sources_dir = bundle / "raw-sources"
    raw_sources_dir.mkdir(exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    new_pages: list[tuple[str, str]] = []  # (slug, title)
    for src, slug in records:
        if not slug:
            print(f"  skip {src.name} (no slug)")
            continue

        # Step 2: copy raw source.
        dest_source = raw_sources_dir / f"{src.name}.raw"
        shutil.copy(src, dest_source)

        # Step 3: write concept page (type=Source, body = source verbatim).
        body = src.read_text(encoding="utf-8")
        title = src.stem
        desc = _description_for(body, fallback=title)
        # Wrap description in double quotes and escape any internal
        # `"` characters — descriptions starting with `>`, `|`, `&`
        # are otherwise interpreted as YAML block-scalar anchors.
        escaped_desc = desc.replace("\\", "\\\\").replace('"', '\\"')
        concept_path = sources_dir / f"{slug}.md"
        concept_path.write_text(
            "---\n"
            "type: Source\n"
            f"title: {title}\n"
            f'description: "{escaped_desc}"\n'
            "tags: [dogfood, source, feishu]\n"
            f"timestamp: {timestamp}\n"
            f"resource: /raw-sources/{src.name}.raw\n"
            "---\n\n"
            f"{body}\n",
            encoding="utf-8",
        )
        new_pages.append((slug, title))

    # Step 4: extend index.md under ## Sources.
    index_path = bundle / "index.md"
    index_text = index_path.read_text(encoding="utf-8")
    lines = index_text.splitlines()
    if "## Sources" not in lines:
        # Insert before any other ## section; if none, append.
        i = len(lines)
        for j, ln in enumerate(lines):
            if ln.startswith("## ") and ln != "## Concepts":
                i = j
                break
        lines.insert(i, "## Sources")
        sources_section_idx = lines.index("## Sources")
    else:
        sources_section_idx = lines.index("## Sources")

    # Existing bullets under ## Sources, to dedupe.
    existing_bullets = set()
    j = sources_section_idx + 1
    while j < len(lines) and lines[j].startswith("*"):
        existing_bullets.add(lines[j])
        j += 1

    new_bullets = [
        f"* [{title}](sources/{slug}.md) — {title}."
        for slug, title in new_pages
        if f"* [{title}](sources/{slug}.md) — {title}." not in existing_bullets
    ]
    lines = lines[: sources_section_idx + 1] + new_bullets + lines[sources_section_idx + 1 :]
    index_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Step 5: prepend each source's ingest event to log.md newest-first.
    log_path = bundle / "log.md"
    log_text = log_path.read_text(encoding="utf-8") if log_path.exists() else "# Directory Update Log\n"
    log_lines = log_text.splitlines()

    head: list[str] = []
    if log_lines and log_lines[0].startswith("# ") and not log_lines[0].startswith("## "):
        head = [log_lines[0]]
        rest = log_lines[1:]
    else:
        head = ["# Directory Update Log"]
        rest = log_lines

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    new_block_lines = []
    for src, slug in records:
        if not slug:
            continue
        new_block_lines.append(f"## {today} ingest | {src.name}")
        new_block_lines.append("")
        new_block_lines.append(
            f"Preserved in `raw-sources/{src.name}.raw` and described by `sources/{slug}.md`."
        )
        new_block_lines.append("")
    final_log = head + new_block_lines + rest
    log_path.write_text("\n".join(final_log) + "\n", encoding="utf-8")

    print(f"wrote {len(new_pages)} Source pages into {bundle}")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", required=True, type=Path)
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    args = parser.parse_args(argv)
    bootstrap(args.corpus, args.bundle, args.config)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
