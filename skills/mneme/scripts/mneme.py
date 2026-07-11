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
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(f'bundle_path = "{bundle_path}"\n', encoding="utf-8")


def _resolve_bundle(config: Path):
    sys.path.insert(0, str(Path(__file__).parent))
    from tools_helpers import resolve_bundle

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
        import indexlib

        result = indexlib.reindex_bundle(str(bundle), indexlib.default_embed_fn())
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
        import indexlib

        hits = indexlib.search_bundle(
            bundle,
            args.query,
            k=args.limit,
            concept_type=args.concept_type,
        )
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
    return parser


def main(argv) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code)
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
