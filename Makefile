# Mneme 测试入口。详见 TESTING.md 与
# docs/superpowers/plans/2026-07-12-mneme-test-strategy.md。
.PHONY: test test-fast test-full test-cov test-news clean

# 默认:跑除 network 外的全部(约 126 测试,~15s)
test:
	.venv/bin/python -m pytest

# fast:只跑 unit 层(约 60 测试,<2s)
test-fast:
	.venv/bin/python -m pytest -m "unit"

# full:跑全部含 network(约 141 测试,60-90s;需要网络)
test-full:
	.venv/bin/python -m pytest -m ""

# cov:跑除 network 外的全部 + coverage 报告
test-cov:
	.venv/bin/python -m coverage run -m pytest
	.venv/bin/python -m coverage report -m
	.venv/bin/python -m coverage xml

# news:只跑黑盒新闻测试(7 测试,~1s)
test-news:
	.venv/bin/python -m pytest tests/test_blackbox_news.py -v

clean:
	rm -f .coverage coverage.xml
	rm -rf .pytest_cache tests/.pytest_cache
