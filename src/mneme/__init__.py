"""mneme — lightweight OKF v0.1 LLM knowledge wiki.

The package is the implementation surface; the agent skill lives under
``mneme/skill/SKILL.md`` and is installed via ``package_data``.
"""

from __future__ import annotations

__version__ = "0.3.0"

# Re-export so legacy callers (and existing tests) can keep using
# ``import mneme; mneme.main(args)``.
from .cli import main  # noqa: E402,F401
