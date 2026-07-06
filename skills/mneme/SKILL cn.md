---
name: mneme
description: "维护一个本地的、符合 OKF 规范的 LLM 知识 wiki。适用于用户想将论文/文章/笔记摄入 wiki、查询 wiki、检查 OKF 合规性，或初始化一个新的 wiki。触发词：'mneme'、'my wiki'、'ingest this'、'query my notes'、'lint the wiki'、'knowledge base'、'查 wiki'、'摄入笔记'、'知识库'。"
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

mneme 用于维护一个外部的 OKF v0.1 wiki，承载研究/学习笔记。你是它严格自律的维护者（schema 层）。共有三条工作流：**ingest**、**query**、**lint**（以及 **init**）。

## 第 0 步：解析 bundle（每次操作都必须执行）

按以下顺序查找 wiki bundle；命中第一个就使用它：
1. `~/.config/mneme/config.toml` 中的 `bundle_path` 键。
2. `MNEME_BUNDLE` 环境变量。
3. 用户在本次请求中显式给出的路径。
4. 自动发现：从当前工作目录向上遍历，寻找根目录下的 `index.md`，其 frontmatter 中必须包含 `okf_version`。
5. 如果存在 `./wiki`，则使用它。
6. 若仍未找到，则询问用户提供路径，或建议执行 `init`。

`config.toml` 采用简单的 `key = "value"` 行格式；用标准库解析即可（不需要 PyYAML）。

> **相对 Skill 的路径：** 像 `scripts/validate_okf.py` 这样的路径，相对于当前 skill 自身所在目录（即包含此 `SKILL.md` 的文件夹）。运行时请从该目录执行，或基于你加载本文件时的路径解析 skill 目录。

## OKF v0.1 合规性（硬性规则，写入时绝不可违反）

1. 每个非保留的 `.md` 文件都必须包含一个由 `---` 分隔的 YAML frontmatter 块。
2. 每个 frontmatter 都必须包含非空的 `type`。
3. 保留文件 `index.md`（目录索引；除根 `okf_version` 外不应有 frontmatter）和 `log.md`（按日期前缀组织的时间线）必须遵循各自的结构。

不要因为以下情况而拒绝写入：未知的 `type` 值、额外的 frontmatter 键、或损坏的链接——这些只应作为 warning。

## type 词汇表（推荐使用，非注册制）

`Concept`（概念/主题）· `Reference`（提炼后的外部来源）· `Summary`（综合总结）· `Source`（位于 `sources/` 下的原始文档）

## ingest <source path>

1. 解析 bundle（第 0 步）。如果不存在且用户愿意，则执行 `init`。
2. 读取源文件（v1 仅支持 `.md`/`.txt`）。复制到 `sources/<slug>.md`（不可变的原始层）。
3. 读取源内容；如有需要，可以与用户讨论其中的关键点。
4. 在合适的子目录下写入 concept 页面，每个页面都带有如下 frontmatter：`type`、`title`、`description`、`tags`、`timestamp`（ISO 8601）、`resource`（源文件路径）。
5. 更新相关的已有页面并添加交叉链接（使用 bundle 相对的绝对路径，如 `/dir/concept.md`）。
6. 更新 `index.md`：在合适的章节下新增 `* [Title](path) - description`。
7. 追加到 `log.md`：`## YYYY-MM-DD ingest | <title>`，再附上一行简要说明。
8. 运行 `python3 scripts/validate_okf.py <bundle>`。在 ingest 完成前，必须修复所有 ERROR。

## query <question>

1. 解析 bundle。
2. 先读取 `index.md`（渐进式披露），定位相关页面。
3. 读取这些页面。
4. 给出综合答案，并附带引用（bundle 相对链接，以及页面中已有的外部引用）。
5. 如果答案具有较强的通用价值，且当前没有页面覆盖该主题，则**主动提出**补写为新的 concept 页面（v1 中不要自动写入）。

## lint

1. 解析 bundle。
2. 运行 `python3 scripts/validate_okf.py <bundle>`。报告 ERROR（必须修复）与 WARNing。
3. 对 warning 做整理和策展：识别相互矛盾的内容、陈旧断言、孤儿页面、缺失的交叉链接、以及尚无页面的重要概念。提出修复建议；只有获得用户批准后才执行修改。

## init <path>

脚手架化创建一个新的空 bundle，并记录路径：
- `<path>/index.md`：包含 `okf_version: "0.1"` frontmatter，以及空的 `# Concepts` 正文。
- `<path>/log.md`：包含 `# Directory Update Log` 标题。
- `<path>/sources/.gitkeep`
- 将 `bundle_path = "<path>"` 写入 `~/.config/mneme/config.toml`（如果需要则创建 `~/.config/mneme/`）。

## 参考资料（按需加载）

`references/workflow-ingest.md` · `references/workflow-query.md` · `references/workflow-lint.md` · `references/type-vocab.md`。校验器：`scripts/validate_okf.py`（位于本 skill 目录）。OKF 规范：<https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md>。
