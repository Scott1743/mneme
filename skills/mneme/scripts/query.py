"""mneme query: a Strands agent that answers from the wiki with citations."""
from __future__ import annotations

import sys
from strands import Agent
from tools import search_index, read_concept, list_concepts

SYSTEM = """You are mneme's query agent. For a question, call search_index to get top-k
relevant chunks, read the full concept pages they belong to, and synthesize an answer WITH
citations (bundle-relative links to the concept pages). If the wiki lacks coverage, say so
and suggest an ingest — never fabricate. If the answer is broadly useful and no page covers
it, offer (do not auto-create) to backfill it."""


def build_agent():
    return Agent(system_prompt=SYSTEM, tools=[search_index, read_concept, list_concepts])


def run(args) -> int:
    if not args:
        print("usage: mneme query <question>", file=sys.stderr)
        return 2
    agent = build_agent()
    print(str(agent(" ".join(args))))
    return 0