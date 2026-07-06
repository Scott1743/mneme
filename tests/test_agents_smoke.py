import os
import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="needs ANTHROPIC_API_KEY to actually run the agent",
)


def test_ingest_agent_imports():
    from ingest import build_agent
    a = build_agent()
    assert a is not None


def test_query_agent_imports():
    from query import build_agent
    assert build_agent() is not None


def test_lint_agent_imports():
    from lint import build_agent
    assert build_agent() is not None