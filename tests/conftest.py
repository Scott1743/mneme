import os
import sys
from pathlib import Path

# Skill-first layout: the implementation lives at
# skills/mneme/scripts/mneme/. conftest adds this directory to sys.path
# so tests can `from mneme import ...` without editable install. We also
# export it via PYTHONPATH so subprocess invocations (`python -m mneme`,
# `python validate_okf.py`) can find the package — important for the
# release-gate entrypoint tests, which run the CLI in a fresh venv.
_SKILL_SCRIPTS = str(Path(__file__).parent.parent / "skills" / "mneme" / "scripts")
sys.path.insert(0, _SKILL_SCRIPTS)
os.environ["PYTHONPATH"] = _SKILL_SCRIPTS + os.pathsep + os.environ.get("PYTHONPATH", "")
