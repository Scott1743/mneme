"""mneme ingest: a Strands agent that reads a source and writes concept pages."""
from __future__ import annotations

import sys
from strands import Agent
from tools import (read_source, list_concepts, read_concept, write_concept,
                   update_index_md, append_log, validate)

SYSTEM = """You are mneme's ingest agent. Given a source file, read it, decide how to
decompose it into atomic concept pages, write each as an OKF concept (frontmatter with
non-empty type, title, description, tags, timestamp, resource), cross-link related pages
using absolute bundle-relative links (/dir/concept.md), update the bundle's index.md via
update_index_md, and append a dated entry to log.md via append_log. Always validate at the
end and fix any ERROR. One source may yield 5-15 pages. Use the tools provided."""


def build_agent():
    return Agent(system_prompt=SYSTEM, tools=[read_source, list_concepts, read_concept,
                                              write_concept, update_index_md, append_log, validate])


def run(args) -> int:
    if not args:
        print("usage: mneme ingest <source_path>", file=sys.stderr)
        return 2
    source = args[0]
    agent = build_agent()
    result = agent(f"Ingest the source at {source} into the wiki. Use the tools to resolve the bundle, write concept pages, update index.md and log.md, then validate.")
    print(str(result))
    return 0