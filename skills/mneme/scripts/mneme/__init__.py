"""mneme — lightweight OKF v0.1 LLM knowledge wiki.

The implementation lives in this package; the agent skill ships
alongside at ``skills/mneme/SKILL.md`` (skill.sh layout, no wheel).
"""

from __future__ import annotations

__version__ = "4.5.0"

from .cli import main  # noqa: E402,F401
