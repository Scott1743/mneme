# 参考资料与生态地图

采集日：2026-07-06。检索方法见 [`README.md`](README.md)（WebSearch 不可用，经 Bing + GitHub raw/API 获取）。

## 官方规范与仓库

| 来源 | 链接 | 说明 |
|---|---|---|
| OKF 规范原文 | <https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md> | OKF v0.1 Draft，本项目合规依据。verbatim 副本见 [`upstream/OKF-SPEC.md`](upstream/OKF-SPEC.md)。 |
| OKF 仓库 README | <https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/README.md> | 含参考 agent、可视化器、示例 bundle 说明。verbatim 副本见 [`upstream/OKF-README.md`](upstream/OKF-README.md)。 |
| OKF 仓库 | <https://github.com/GoogleCloudPlatform/knowledge-catalog> | GoogleCloudPlatform 官方，MIT。含 `okf/`（规范+参考实现）、`bundles/`（GA4 / Stack Overflow / Bitcoin 三个示例 bundle）、`samples/`（recipe）、`toolbox/`。 |
| OKF 站点 | <https://okf.md/> | “3 rules, not 300.” 宣传站 + 在线校验器 + skill 安装入口。 |

## 思想源头

| 来源 | 链接 | 说明 |
|---|---|---|
| Karpathy *LLM Wiki* gist | <https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f> | 2026-04-04 发布。三层架构 + ingest/query/lint + index.md/log.md 的原始表述。OKF 官方博客称其“把这个想法说得最为干脆”。中文梳理（MIT）见 [`upstream/karpathy-llm-wiki.md`](upstream/karpathy-llm-wiki.md)。 |

## 中文社区解读（链接，非副本）

以下为中文博客对 OKF 的解读，仅作背景阅读；其内容版权归原作者，本仓库不复制其正文。

| 来源 | 链接 | 一句话 |
|---|---|---|
| 博客园 · iTech | <https://www.cnblogs.com/itech/p/20581987> | “Google 发布 Open Knowledge Format：给 AI Agent 喂知识的标准格式”——综述 OKF 动机、bundle 结构、Karpathy 谱系、AI 知识栈定位、HN 社区争议。 |
| 知乎专栏 | <https://zhuanlan.zhihu.com>（搜 “OKF Open Knowledge Format”） | 把 OKF 从设计理念到文件格式到实际场景讲清楚。 |
| 51CTO | <https://www.51cto.com/article/>（搜 “OKF 格式本身不是平台”） | 强调 OKF 不绑定云 / 数据库 / 模型厂商 / agent 框架，读写无需专有账号或 SDK。 |
| blog.frognew | <https://blog.frognew.com/open-knowledge-format.html> | “OKF 解决的不是 Google 自己的问题，而是每个在构建 AI Agent 的团队都在重复解决的问题。” |
| dranixj | <https://dranixj.com/articles/google-open-knowledge-format> | OKF v0.1 综述：把散落在 Wiki、数据目录的知识用纯 Markdown + YAML frontmatter 统一。 |

## 生态与工具（GitHub）

| 仓库 | 语言 | 形态 |
|---|---|---|
| [`yzfly/awesome-okf`](https://github.com/yzfly/awesome-okf) | — | **中文世界 OKF 落点**：规范翻译、7 个 producer 插件（feishu/obsidian/notion/github/awesome/html→okf + myokf-cli）、7 个 Claude Code skill、3 份向上游扩展提案。仓库自身是 OKF bundle（dogfooding）。 |
| [`JuneYaooo/lineage-skill`](https://github.com/JuneYaooo/lineage-skill) | Python | 带出处（lineage）蒸馏的 agent skill，输出 OKF 包。 |
| [`sniperunder123/okf-knowledge`](https://github.com/sniperunder123/okf-knowledge) | Python | Claude Code `/okf` skill。 |
| [`longsizhuo/okf-frontmatter`](https://github.com/longsizhuo/okf-frontmatter) | Python | 把仓库文档维护成 OKF 形态的 skill。 |
| [`scaccogatto/okf-skills`](https://github.com/scaccogatto/okf-skills) | Python | Claude Code 的 OKF 技能。 |
| [`xSAVIKx/okf-skills`](https://github.com/xSAVIKx/okf-skills) | Go | Go 实现的 OKF agentic skills。 |
| [`Sudhakaran88/okf-conformance`](https://github.com/Sudhakaran88/okf-conformance) | JS | OKF 一致性校验器（实现 §9 规则的参考）。 |
| [`killop/okf-rag`](https://github.com/killop/okf-rag) | Rust | 本地优先 OKF 检索 / RAG（规模化时可选外挂）。 |
| [`0dust/OKFy`](https://github.com/0dust/OKFy) | TS | 文档 → agent 可读 OKF bundle 转换器。 |
| [`psinetron/echoes-vault-opencode`](https://github.com/psinetron/echoes-vault-opencode) | TS | OpenCode 持久记忆插件，底层用 OKF。 |
| [`EliaszDev/hermes-okf`](https://github.com/EliaszDev/hermes-okf) | Python | 基于 OKF 的 agent 持久记忆（PyPI）。 |
| [`pumblus/okf-harness`](https://github.com/pumblus/okf-harness) | TS | 本地优先的 agent 终端 harness。 |
| [`superops-team/okf`](https://github.com/superops-team/okf) | Go | 项目级知识库。 |
| [`taikunudel/wiki-as-an-mcp`](https://github.com/taikunudel/wiki-as-an-mcp) | Python | 首个通用 Wiki MCP server（OKF 与 MCP 桥接的参考）。 |

### awesome-okf 提供的 Claude Code skills（mneme 可对标/复用）

`okf-creator`（从零创建合规知识库）、`code-to-okf`（代码库转 OKF）、`book-to-okf`（书/长文拆成互链概念库）、`github-to-okf`（仓库→OKF 富化）、`awesome-to-okf`（导入 awesome 列表）、`okf-to-book`（发布为 VitePress 文档站）、`okf-to-web`（打包成单文件网页含图谱）。

### 三份向上游扩展提案（向后兼容，不动任何 MUST）

- **i18n**：`lang` + `canonical`（多语言/镜像源）。
- **代码支持**：类型词表、符号引用、行号锚点。
- **HTML 一等公民**：`.html` 概念，双表示。

## 配套工具（Karpathy 原文提到）

- [`qmd`](https://github.com/tobi/qmd)——本地 Markdown 搜索引擎（BM25 + 向量 + LLM 重排），有 CLI 也有 MCP server。规模化时可选的检索外挂。
- Obsidian Web Clipper、Obsidian 图谱视图、Marp（Markdown 幻灯片）。

## Mneme 的差异化

mneme 不与上述生态竞争功能，而追求**最小收束**：本地优先、零第三方依赖、面向个人/小团队、把 Karpathy 思想 + OKF 契约落成一个开箱即用的 agent skill。可对标 `okf-creator`，但更轻、无云依赖、强调 ingest/query/lint 三工作流的纪律性。
