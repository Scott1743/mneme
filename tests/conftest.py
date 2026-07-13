import os
import sys
from pathlib import Path

# v1.1.0 起,实现位于 skills/mneme/scripts/mneme/（skill-first 交付）。conftest 在
# pytest 启动时被自动加载,这里把 skills/mneme/scripts/ 加入 sys.path,使所有测试
# 都能 `from mneme import ...` 而无需 editable install。这是 skill-first 布局的
# 标准做法,删除会导致 `ModuleNotFoundError: No module named 'mneme'`。
#
# 同时把同一路径注入 PYTHONPATH,让 subprocess 调用的 `python -m mneme` /
# `python validate_okf.py` 也能找到包。
#
# 详见 docs/superpowers/plans/2026-07-13-mneme-1.1.0-implementation.md §3.3。
_SKILL_SCRIPTS = str(Path(__file__).parent.parent / "skills" / "mneme" / "scripts")
sys.path.insert(0, _SKILL_SCRIPTS)
os.environ["PYTHONPATH"] = _SKILL_SCRIPTS + os.pathsep + os.environ.get("PYTHONPATH", "")
