"""mneme lint: a Strands agent that curates the wiki."""
from __future__ import annotations

import sys
from strands import Agent
from tools import validate, find_orphans, list_concepts, read_concept

SYSTEM = """You are mneme's lint agent. Run validate (fix hard ERRORs), find_orphans, and
review for stale pages (old timestamp, no log entry), missing cross-links between related
concepts, and important concepts with no page. Propose fixes; do not apply without approval."""


def build_agent():
    return Agent(system_prompt=SYSTEM, tools=[validate, find_orphans, list_concepts, read_concept])


def run(args) -> int:
    agent = build_agent()
    print(str(agent("Lint the wiki. Report errors and curation suggestions.")))
    return 0