#!/usr/bin/env python3
"""Thin mneme CLI for bundle setup and deterministic L2 operations."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List

def _default_config_path() -> Path:
    from .config import resolve_config_dir

    return resolve_config_dir() / "config.toml"


def _limit(value: str) -> int:
    parsed = int(value)
    if not 1 <= parsed <= 100:
        raise argparse.ArgumentTypeError("must be between 1 and 100")
    return parsed


def _query(value: str) -> str:
    if not value.strip():
        raise argparse.ArgumentTypeError("must not be empty")
    return value


def _write_config(bundle_path: Path, config_path: Path) -> None:
    from .config import write_config
    config_path.parent.mkdir(parents=True, exist_ok=True)
    write_config(config_path, {"bundle_path": str(bundle_path)})


def _resolve_bundle(args: argparse.Namespace) -> Path | None:
    explicit = getattr(args, "bundle", None)
    if explicit:
        bundle = Path(explicit)
        return bundle if bundle.is_dir() else None

    from .tools_helpers import resolve_bundle

    config_path = getattr(args, "config", None)
    if not config_path:
        config_path = _default_config_path()
    config_dir = Path(config_path).parent
    return resolve_bundle(config_dir=config_dir, env=None, cwd=Path.cwd())


def cmd_init(args: argparse.Namespace) -> int:
    bundle = Path(args.path)
    config = Path(args.config)
    if bundle.exists():
        print(f"bundle already exists: {bundle}", file=sys.stderr)
        return 1
    bundle.mkdir(parents=True)
    (bundle / "sources").mkdir(exist_ok=True)
    (bundle / "sources" / ".gitkeep").touch(exist_ok=True)
    if not (bundle / "index.md").exists():
        (bundle / "index.md").write_text(
            '---\nokf_version: "0.1"\n---\n\n# Concepts\n', encoding="utf-8"
        )
    if not (bundle / "log.md").exists():
        (bundle / "log.md").write_text("# Directory Update Log\n", encoding="utf-8")
    _write_config(bundle, config)
    print(f"initialized bundle at {bundle}; recorded in {config}")
    return 0


def cmd_reindex(args: argparse.Namespace) -> int:
    """v2.0 reindex: rebuild the L1 (sqlite3 + FTS5) index.

    Walks ``*.md`` under the bundle (excluding ``.mneme/``, ``sources/``,
    and ``external-sources/``), parses each page's frontmatter, and writes
    one ``pages`` row + ``pages_fts`` insertion per page via Task 3's
    atomic snapshot rebuild. L2 (sqlite-vec + FastEmbed) is deferred to
    v2.1 — no auto-install, no surprise network calls.
    """
    bundle = _resolve_bundle(args)
    if bundle is None:
        print("no bundle found; set bundle_path, MNEME_BUNDLE, or run mneme init", file=sys.stderr)
        return 1
    from . import indexlib

    bundle = Path(bundle)
    paths: list[Path] = []
    for p in sorted(bundle.rglob("*.md")):
        if not p.is_file():
            continue
        parts = p.relative_to(bundle).parts
        if any(part == ".mneme" for part in parts):
            continue
        if "sources" in parts:
            continue
        if "external-sources" in parts:
            continue
        paths.append(p)

    try:
        indexed = indexlib.reindex_paths(paths, bundle)
    except Exception as exc:
        print(f"reindex failed: {exc}", file=sys.stderr)
        return 1
    print(f"indexed {indexed} page(s) into {bundle / '.mneme' / 'index.db'}")
    return 0


# v2.0 search surface — see
# docs/superpowers/plans/2026-07-13-mneme-2.0-implementation.md Task 4.
# Search returns *candidates* (path + title + snippet) only; the host
# agent reads each candidate page in full to compose the final answer.
# Two paths:
#   1. FTS5 against <bundle>/.mneme/index.db (default; built by
#      `mneme reindex` via Task 3's reindex_paths).
#   2. L0 grep fallback over *.md when index.db is missing.
# No L2 deps (sqlite-vec + fastembed) are imported here; those land
# in v2.1.

_L0_GREP_CONTEXT = 60  # chars of context around the matched line


def _cmd_search_grep(bundle: Path, query: str, k: int) -> Dict:
    """L0 fallback: walk ``*.md`` files in the bundle, parse
    frontmatter for the title, and case-insensitively scan the body
    for ``query``. Returns the same ``{"query": ..., "candidates": [...]}``
    shape as :func:`indexlib.search` so the caller doesn't branch.
    """
    from . import okflib

    q = query.lower()
    candidates: List[Dict] = []
    for md_path in sorted(bundle.rglob("*.md")):
        if not md_path.is_file():
            continue
        parts = md_path.relative_to(bundle).parts
        if any(part == ".mneme" for part in parts):
            continue
        # Raw sources under sources/ are immutable inputs — they have
        # no frontmatter and shouldn't be surfaced as OKF concepts.
        if "sources" in parts:
            continue
        if md_path.name in ("index.md", "log.md"):
            continue
        try:
            text = md_path.read_text(encoding="utf-8")
        except OSError:
            continue
        parsed = okflib.parse_frontmatter(text)
        title = ""
        body = text
        if parsed is not None:
            meta, body = parsed
            title = str(meta.get("title", "") or "")
        if q not in title.lower() and q not in body.lower():
            continue
        snippet = _make_grep_snippet(body, q, _L0_GREP_CONTEXT)
        rel = md_path.relative_to(bundle).as_posix()
        candidates.append({"path": rel, "title": title, "snippet": snippet})
        if len(candidates) >= k:
            break
    return {"query": query, "candidates": candidates}


def _make_grep_snippet(body: str, query_lower: str, context: int) -> str:
    """Build a short snippet around the first body match of ``query_lower``.

    Truncates to a single line so the agent's candidate list stays
    scannable; falls back to a head-of-body snippet when no match
    exists (which shouldn't happen because the caller already
    filtered on the match, but keeps the function defensive).
    """
    lines = body.splitlines()
    for line in lines:
        if query_lower in line.lower():
            stripped = line.strip()
            if len(stripped) <= context * 2:
                return stripped
            idx = stripped.lower().find(query_lower)
            start = max(0, idx - context)
            end = min(len(stripped), idx + len(query_lower) + context)
            return stripped[start:end]
    # Defensive fallback — body had the match per the caller, but no
    # single line did (e.g. match spans a line boundary). Trim head.
    head = " ".join(lines).strip()
    return head if len(head) <= context * 2 else f"{head[: context * 2]}..."


def cmd_search(args: argparse.Namespace) -> int:
    """v2.0 search: candidates + snippets via FTS5, L0 grep fallback."""
    bundle = _resolve_bundle(args)
    if bundle is None:
        print(
            "no bundle found; set bundle_path, MNEME_BUNDLE, or run mneme init",
            file=sys.stderr,
        )
        return 1

    from . import indexlib

    db = bundle / ".mneme" / "index.db"
    if db.is_file():
        try:
            out = indexlib.search(args.query, db, k=args.limit)
        except Exception as exc:
            print(f"search failed: {exc}", file=sys.stderr)
            return 1
    else:
        # L0 grep fallback. Don't write the index here — the user
        # opted out of `mneme reindex`. Just nudge on stderr.
        print(
            f"no index at {db}; falling back to L0 grep. "
            "Run `mneme reindex` for full-text ranking.",
            file=sys.stderr,
        )
        out = _cmd_search_grep(bundle, args.query, args.limit)

    if args.json:
        print(json.dumps(out, ensure_ascii=False))
    else:
        for candidate in out["candidates"]:
            # FTS5 snippet() may return multi-line fragments (e.g.
            # `# h\n|rareword| appears here\n`); collapse to a single
            # line so the tab-separated human output stays scannable.
            snippet = candidate["snippet"].replace("\n", " ").strip()
            print(
                f"{candidate['path']}\t{candidate['title']}\t{snippet}"
            )
    return 0


def cmd_dream(args: argparse.Namespace) -> int:
    """Read-only dream audit.

    Surfaces a candidate audit report (OKF candidates, Mneme writer-rule
    candidates, navigation candidates) for the agent to review. Writes
    happen in the SKILL.md workflow after the user explicitly approves
    the report — never from this CLI. There is no ``--apply`` flag by
    design.
    """
    from . import dream as _dream

    if getattr(args, "bundle", None):
        bundle = Path(args.bundle)
    else:
        bundle = _resolve_bundle(Path(args.config))
    if bundle is None:
        print(
            "no bundle found; pass --bundle or set MNEME_BUNDLE / "
            "$config_dir/config.toml [bundle_path], or run `mneme init`",
            file=sys.stderr,
        )
        return 1
    report = _dream.dream_audit(bundle)
    if getattr(args, "json", False):
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        # Human-readable summary: counts + candidate rules + paths.
        meta = report.get("_meta", {})
        candidates = meta.get("candidate_count", 0)
        print(f"dream audit (read-only) — {candidates} candidate page(s)")
        print(f"  raw_distance_only: {meta.get('raw_distance_only')}")
        print(f"  writes: {meta.get('writes')}")
        for section in ("okf_hard_rules", "mneme_writer_rules"):
            items = report.get(section, [])
            if not items:
                continue
            print(f"  {section}:")
            for it in items:
                print(f"    - {it['path']}: [{it['rule']}]")
        nav = report.get("navigation", {})
        for k, v in nav.items():
            if v:
                print(f"  navigation.{k}: {len(v)}")
    return 0


def cmd_lint(args: argparse.Namespace) -> int:
    """Validate one bundle; exit 1 only when OKF ERROR diagnostics exist.

    Pipeline (Task 5 — see
    docs/superpowers/plans/2026-07-13-mneme-2.0-implementation.md):
      1. :func:`okflib.lint_bundle` — wraps :func:`okflib.validate_bundle`
         and appends MNEME-TAG-MISSING for concept pages lacking
         ``tags``. The base OKF validator is *not* reimplemented; the
         wrapper only translates its ``Report`` into flat diagnostics.
      2. :func:`okflib.find_orphans` — orphan analysis (always printed).

    Exit codes (frozen by Pre-Task B):
      0 — no ERROR diagnostics (WARN-only bundles exit 0).
      1 — at least one ERROR diagnostic, OR the bundle could not be
          resolved.
    """
    explicit = getattr(args, "path", None)
    if explicit:
        args = argparse.Namespace(
            bundle=explicit,
            **{k: v for k, v in vars(args).items() if k not in {"path", "bundle"}},
        )
    bundle = _resolve_bundle(args)
    if bundle is None:
        print("no bundle found; set bundle_path, MNEME_BUNDLE, or run mneme init", file=sys.stderr)
        return 1

    from . import okflib

    report = okflib.lint_bundle(bundle, require_tags=True)
    diagnostics = report.get("diagnostics", [])

    errors_count = 0
    warnings_count = 0
    for d in diagnostics:
        # Same `{SEVERITY}  {path}: [{rule}] {detail}` shape as
        # `validate_okf.print_report` so existing log parsers
        # (test_e2e_lint._parse_report etc.) keep working.
        if d["severity"] == "ERROR":
            errors_count += 1
        else:
            warnings_count += 1
        print(f"{d['severity']}  {d['path']}: [{d['code']}] {d['detail']}")
    print(f"\n{errors_count} error(s), {warnings_count} warning(s)")

    orphans = okflib.find_orphans(bundle)
    print(f"\norphan concept pages ({len(orphans)}):", file=sys.stderr)
    for slug in orphans:
        print(f"  - {slug}", file=sys.stderr)
    return 1 if errors_count else 0


def cmd_dream(args: argparse.Namespace) -> int:
    """Read-only dream audit thin wrapper (real logic in dream.dream_audit)."""
    from . import dream as _dream
    if getattr(args, "bundle", None):
        bundle = Path(args.bundle)
    else:
        bundle = _resolve_bundle(Path(args.config))
    if bundle is None:
        return 1
    report = _dream.dream_audit(bundle)
    if getattr(args, "json", False):
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        meta = report.get("_meta", {})
        candidates = meta.get("candidate_count", 0)
        print(f"dream audit (read-only) — {candidates} candidate page(s)")
        for section in ("okf_hard_rules", "mneme_writer_rules"):
            items = report.get(section, [])
            if not items:
                continue
            print(f"  {section}:")
            for it in items:
                print(f"    - {it['path']}: [{it['rule']}]")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mneme")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="scaffold an OKF bundle")
    init_parser.add_argument("path")
    init_parser.add_argument("--config", default=None)
    init_parser.set_defaults(handler=cmd_init)

    lint_parser = subparsers.add_parser(
        "lint", help="validate the bundle (OKF MUSTs + diagnostics)"
    )
    lint_parser.add_argument("path", nargs="?", default=None)
    lint_parser.add_argument("--bundle", dest="bundle", default=None)
    lint_parser.add_argument("--config", default=None)
    lint_parser.set_defaults(handler=cmd_lint)

    reindex_parser = subparsers.add_parser("reindex", help="rebuild the search index")
    reindex_parser.add_argument("--bundle", dest="bundle", default=None)
    reindex_parser.add_argument("--config", default=None)
    reindex_parser.set_defaults(handler=cmd_reindex)

    search_parser = subparsers.add_parser("search", help="return ranked candidates from the index")
    search_parser.add_argument("query", type=_query)
    search_parser.add_argument("-k", "--limit", type=_limit, default=10)
    search_parser.add_argument("--type", dest="concept_type", default=None)
    search_parser.add_argument("--bundle", dest="bundle", default=None)
    search_parser.add_argument("--config", default=None)
    search_parser.add_argument("--json", action="store_true")
    search_parser.set_defaults(handler=cmd_search)

    dream_parser = subparsers.add_parser(
        "dream",
        help="read-only audit (writes happen in the SKILL.md workflow, after user approval)",
    )
    dream_parser.add_argument(
        "--bundle",
        dest="bundle",
        default=None,
        help="bundle path (default: resolve via $MNEME_BUNDLE / config.toml)",
    )
    dream_parser.add_argument("--config", default=None)
    dream_parser.add_argument("--json", action="store_true")
    dream_parser.set_defaults(handler=cmd_dream)
    return parser



def main(argv=None) -> int:
    """CLI entry point.

    Accepts an optional ``argv`` list so callers can drive it from Python
    (tests, embedding hosts). When invoked as a console script via the
    ``[project.scripts]`` entry point, setuptools generates a stub that
    calls ``main()`` with no arguments — ``argv=None`` resolves that case
    to ``sys.argv[1:]``.
    """
    import sys
    if argv is None:
        argv = sys.argv[1:]
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code)
    return args.handler(args)
