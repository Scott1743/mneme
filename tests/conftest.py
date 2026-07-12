import sys
from pathlib import Path

# v0.3.0 起,实现位于 src/mneme/ 而非 scripts/。conftest 在 pytest 启动时
# 被自动加载,这里把 src/ 加入 sys.path,使所有测试都能 `from mneme import ...`
# 而无需 editable install。这是 src layout 的标准做法,删除会导致
# `ModuleNotFoundError: No module named 'mneme'`。
#
# 详见 docs/superpowers/plans/2026-07-12-mneme-test-strategy.md §6 fixture 策略。
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
