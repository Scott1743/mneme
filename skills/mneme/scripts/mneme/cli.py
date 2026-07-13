#!/usr/bin/env python3
"""Thin mneme CLI for bundle setup and deterministic L2 operations."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

CONFIG_DEFAULT = Path.home() / ".config" / "mneme" / "config.toml"


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


def _resolve_bundle(config: Path):
    from .tools_helpers import resolve_bundle
    return resolve_bundle(config_path=config)


def cmd_init(args: argparse.Namespace) -> int:
    bundle = Path(args.path)
    config = Path(args.config)
    bundle.mkdir(parents=True, exist_ok=True)
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
    bundle = _resolve_bundle(Path(args.config))
    if bundle is None:
        print("no bundle found; set bundle_path, MNEME_BUNDLE, or run mneme init", file=sys.stderr)
        return 1
    try:
        from . import indexlib

        result = indexlib.reindex_bundle(str(bundle), indexlib.default_embed_fn())
    except ImportError as exc:
        # L2 deps (sqlite-vec + fastembed) are NOT bundled with the skill.
        # OKF core stays zero-dep; L2 is opt-in. Tell the user plainly
        # what to install — no auto-install, no surprise network calls.
        print(
            "L2 indexing needs sqlite-vec + fastembed, which are not part "
            "of the skill bundle.\n"
            "Install them once with:\n"
            "  pip install 'sqlite-vec>=0.1.9,<0.2' 'fastembed>=0.8.0,<0.9'\n"
            f"(then re-run this command)\n\n"
            f"Underlying error: {exc}",
            file=sys.stderr,
        )
        return 1
    except Exception as exc:
        print(f"reindex failed: {exc}", file=sys.stderr)
        return 1
    print(
        f"indexed {result.indexed_concepts} concepts / {result.indexed_chunks} chunks "
        f"({result.skipped_concepts} skipped) into {result.db_path}"
    )
    return 0


def _snippet(text: str, limit: int = 180) -> str:
    normalized = " ".join(text.split())
    return normalized if len(normalized) <= limit else f"{normalized[: limit - 3]}..."


def cmd_search(args: argparse.Namespace) -> int:
    bundle = _resolve_bundle(Path(args.config))
    if bundle is None:
        print("no bundle found; set bundle_path, MNEME_BUNDLE, or run mneme init", file=sys.stderr)
        return 1
    try:
        from . import indexlib

        hits = indexlib.search_bundle(
            bundle,
            args.query,
            k=args.limit,
            concept_type=args.concept_type,
        )
    except ImportError as exc:
        print(
            "L2 search needs sqlite-vec + fastembed, which are not part "
            "of the skill bundle.\n"
            "Install them once with:\n"
            "  pip install 'sqlite-vec>=0.1.9,<0.2' 'fastembed>=0.8.0,<0.9'\n"
            f"(then re-run this command)\n\n"
            f"Underlying error: {exc}",
            file=sys.stderr,
        )
        return 1
    except Exception as exc:
        print(f"search failed: {exc}", file=sys.stderr)
        return 1
    ranked = [{"rank": rank, **hit} for rank, hit in enumerate(hits, start=1)]
    if args.json:
        print(json.dumps(ranked, ensure_ascii=False, indent=2))
        return 0
    for hit in ranked:
        print(f"{hit['rank']}. {hit['title']} [{hit['type']}]")
        print(f"   {hit['path']}  distance={hit['distance']:.4f}")
        print(f"   {_snippet(hit['text'])}")
    return 0


# Lint handler exit codes:
#   1 = generic failure (bundle missing, etc.) OR OKF validation has errors
#   3 = OKF validation passed; the orphan section is included in
#       stderr. Code 3 is preserved as the "lint ran and found
#       something to look at" signal — distinct from argparse's 2
#       ("unrecognized subcommand").
LINT_GUARD_RC = 3


def cmd_lint(args: argparse.Namespace) -> int:
    """Curate + report.

    Pipeline:
      1. run OKF v0.1 validation (per PR2 rule table)
      2. run `okflib.find_orphans(bundle)` and print the list on stderr

    Exit codes:
      1 — bundle path is bad, OR the validator found errors
      3 — validator passed; orphan section is included (or empty if
          the bundle has none)
    """
    bundle = Path(args.path)
    if not bundle.is_dir():
        print(f"bundle path is not a directory: {bundle}", file=sys.stderr)
        return 1
    from .validate_okf import print_report, validate_bundle
    rc = print_report(validate_bundle(bundle))

    from . import okflib
    orphans = okflib.find_orphans(bundle)
    print(f"\norphan concept pages ({len(orphans)}):", file=sys.stderr)
    for slug in orphans:
        print(f"  - {slug}", file=sys.stderr)
    return LINT_GUARD_RC if rc == 0 else rc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mneme")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="scaffold an OKF bundle")
    init_parser.add_argument("path")
    init_parser.add_argument("--config", default=str(CONFIG_DEFAULT))
    init_parser.set_defaults(handler=cmd_init)

    reindex_parser = subparsers.add_parser("reindex", help="rebuild the L2 semantic index")
    reindex_parser.add_argument("--config", default=str(CONFIG_DEFAULT))
    reindex_parser.set_defaults(handler=cmd_reindex)

    search_parser = subparsers.add_parser("search", help="return ranked L2 retrieval hits")
    search_parser.add_argument("query", type=_query)
    search_parser.add_argument("-k", "--limit", type=_limit, default=10)
    search_parser.add_argument("--type", dest="concept_type")
    search_parser.add_argument("--config", default=str(CONFIG_DEFAULT))
    search_parser.add_argument("--json", action="store_true")
    search_parser.set_defaults(handler=cmd_search)

    lint_parser = subparsers.add_parser(
        "lint", help="curate + report (OKF validation + orphan analysis)"
    )
    lint_parser.add_argument("path")
    lint_parser.add_argument("--config", default=str(CONFIG_DEFAULT))
    lint_parser.set_defaults(handler=cmd_lint)
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
