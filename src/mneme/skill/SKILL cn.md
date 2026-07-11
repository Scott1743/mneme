---
name: mneme
description: "维护和搜索本地、符合 OKF 的 LLM 知识 wiki。适用于摄入资料、搜索或查询 wiki、检查合规性、重建索引或初始化 wiki。触发词：mneme、my wiki、search my wiki、ingest this、query my notes、lint the wiki、knowledge base、查 wiki、搜索知识库、摄入笔记、知识库。Dream（定时自动维护）在 v0.3.0 中**主动移除**，原因见 CHANGELOG 0.2.1 条目。"
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
  - AskUserQuestion
---

# mneme - 轻量级 LLM wiki

使用原生工具（Read/Write/Edit/Bash/Glob/Grep）和薄 CLI（`mneme init` / `mneme reindex` / `mneme search`）驱动所有操作。不得调用独立 agent SDK 或 `@tool` 框架；宿主 agent 自身就是运行时。

mneme 维护一个外部 OKF v0.1 研究/学习 wiki。共有 7 个场景，按用户意图选择。

## 第 0 步：解析 bundle（每个场景都必须执行）

依次使用第一个命中项：

1. `~/.config/mneme/config.toml` 中的 `bundle_path`。
2. `MNEME_BUNDLE` 环境变量。
3. 用户显式给出的路径。
4. 从 cwd 向上查找根 `index.md`，且其 frontmatter 含 `okf_version`。
5. 已存在的 `./wiki`。
6. 都没有则询问路径，或提出执行 `init`。

辅助命令：

```bash
mneme --help  # 或 python3 -m mneme --help；v0.3.0 起不再需要 sys.path hack
```

`scripts/` 和 `references/` 在安装后位于 `mneme/skill/` 路径下，但作为已安装 skill 使用时无需直接引用。

## OKF v0.1 合规硬约束

1. 每个非保留 `.md` 必须有 `---` 分隔的 YAML frontmatter。
2. 每个 frontmatter 必须包含非空 `type`。
3. 保留文件 `index.md`（除根 `okf_version` 外无 frontmatter）和 `log.md`（日期前缀时间线）遵循规范结构。

未知 `type`、额外 frontmatter 键和断链只能告警，不得拒绝 bundle。

推荐但不注册的 type：`Concept`、`Reference`、`Summary`、`Source`。

## 场景：init <path>

1. 运行 `mneme init <path> [--config <cfg>]`。
2. 验证根 `index.md` 含 `okf_version: "0.1"`，并存在 `log.md` 和 `sources/.gitkeep`。
3. 告知用户 bundle 路径已可被第 0 步发现。

## 场景：reindex [--config <cfg>]

1. 运行 `mneme reindex [--config <cfg>]`。
2. 确认输出中的 concept、chunk、skipped 数量和 `.mneme/index.db` 路径。

每次 ingest 或 dream 新增、删除、移动、合并页面后都必须 reindex。

## 场景：search <query>

只返回排序后的 L2 命中，不综合答案、不修改 bundle：

1. 运行 `mneme search "<query>" --json [--type <type>] [-k <limit>]`。
2. 展示标题、bundle-relative 路径、type 和 snippet。
3. 不自动 reindex；索引缺失或不兼容时，按 CLI 提示建议运行 `mneme reindex`。

查询内容必须作为 shell 参数传递，禁止拼进 Python 源码。snippet 只用于导航，Markdown 概念页才是事实来源。

## 场景：ingest <source path>

将来源（论文/文章/笔记）蒸馏成 OKF 概念页：

0. **保留原始来源（不可变素材）。** 蒸馏前先复制原始文件到 `<bundle>/sources/<basename>`，让原始内容成为 OKF v0.1 的 source-of-truth。若目标已存在且内容不同，应中止并询问用户，禁止覆盖。
1. 读取完整源资料。
2. 按“一页一个原子概念”拆分，单一来源可产生 1-15 个页面。
3. 为每页写 `<bundle>/concepts/<slug>.md`，frontmatter 包含 `type/title/description/tags/timestamp/resource`，并用绝对 bundle-relative 链接交叉引用相关页。
4. 更新 `index.md` 对应章节，条目格式为 `* [Title](path) - description`。
5. 在 `log.md` **顶部**插入（prepend）`## YYYY-MM-DD ingest | <source title>` 和简短说明。OKF v0.1 约定 log 必须 newest-first。
6. 运行 `mneme reindex`，再运行 `validate_okf.py`；完成前修复所有 ERROR。

若 fastembed 模型不可用，应明确提示安装 `mneme[index]`，**不得**用任何替代函数生成生产索引（测试夹具内部另有安排，但绝不出现在给 agent 的指令中）。

详见 `references/workflow-ingest.md`。

## 场景：query <question>

1. 运行 `mneme search "<question>" --json -k 10`。
2. 读取每个命中对应的完整 Markdown 概念页。
3. 综合答案，并以内联绝对 bundle-relative 链接引用页面。
4. 若答案具有长期价值且无页面覆盖，只提出新增 `Summary`，不要自动写入。
5. wiki 覆盖不足时如实说明，并建议 ingest。

详见 `references/workflow-query.md`。

## 场景：lint

1. 运行 `mneme lint <bundle>`，区分 ERROR 与 WARNING。
2. 用 `okflib.find_orphans` 找孤儿页。
3. 抽样阅读页面，识别矛盾、过时论断和缺失交叉引用。
4. 写 `<bundle>/lint-report-<date>.md`，只报告，不自动修改内容。

详见 `references/workflow-lint.md`。

> **dream（定时、全自动）** 在 v0.3.0 中**主动移除**：原实现调用了不存在的 `find_orphans()`、在解析 bundle 前执行 `git add -A`、可能错误提交无关内容。重新引入需通过：(a) Phase 5 retrieval benchmark；(b) `find_orphans` + 相似度安全 workflow 测试；(c) dry-run preview 模式 + 独立安全 TDD。详见 `CHANGELOG.md` 0.2.1 条目。

## 参考资料

`scripts/validate_okf.py` · `references/workflow-ingest.md` · `references/workflow-query.md` · `references/workflow-lint.md` · `references/type-vocab.md` · `references/wiki-structure.md` · `references/index-design.md`。

OKF 规范：<https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md>。
