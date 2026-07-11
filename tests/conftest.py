import sys
from pathlib import Path

# v0.3.0: the implementation lives in src/mneme/ as a real Python package
# rather than a scripts/ directory. Tests import directly from there so
# they don't depend on the symlink at skills/mneme/scripts.
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
