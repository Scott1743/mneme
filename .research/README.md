# .research/

立项前为 mneme 采集的研究资料与约束。本目录是**研究档案**，不是 wiki 本体（wiki 本体将在 `wiki/` 中建立并保持 OKF 合规）。

## 目录

| 路径 | 内容 |
|---|---|
| `constraints.md` | 蒸馏后的硬约束：OKF v0.1 合规规则 + 项目约束 + 命名约定 + 禁止项 |
| `design-rationale.md` | 设计推演：Karpathy LLM Wiki → OKF → agent skill 的谱系与“为什么” |
| `rag-sota-2026.md` | mid-2026 RAG SOTA 调研：指标 / 基准 / embedder / reranker / 方法景观 / Mneme 定位 |
| `rag-benchmarks-2026.md` | RGB / ASQA / PopQA / ELI5 / MS MARCO 五项基准的精确 cite + metric + 原论文与 2024–2026 最佳数字（含 arXiv ID 修正） |
| `references.md` | 全部来源链接 + 生态地图 + 检索方法 |
| `upstream/` | 上游规范原文（MIT，verbatim 副本，**勿改**） |

## `upstream/` provenance

下列文件是上游开源规范/文档的 **verbatim 副本**，未做任何修改（未加 frontmatter、未改正文）。均属 MIT 许可，允许复制与再分发。若上游更新，以原链接为准并同步本副本。

| 文件 | 来源 | 许可 | 采集日 |
|---|---|---|---|
| `upstream/OKF-SPEC.md` | `GoogleCloudPlatform/knowledge-catalog` · `okf/SPEC.md`（v0.1 Draft） | MIT | 2026-07-06 |
| `upstream/OKF-README.md` | 同上 · `okf/README.md` | MIT | 2026-07-06 |
| `upstream/karpathy-llm-wiki.md` | `yzfly/awesome-okf` · `docs/karpathy-llm-wiki-zh.md`（整理者：云中江树） | MIT | 2026-07-06 |

`karpathy-llm-wiki.md` 是对 Andrej Karpathy 2026-04-04 发布的 *LLM Wiki* gist 的中文梳理，原文链接：
<https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f>

## 检索方法说明

本机位于中国大陆，网络环境受限，常规检索通道不可用：

- **WebSearch 工具**：返回空占位文本，不可用（US-only 且被阻断）。
- **Wikipedia / DuckDuckGo**：DNS 被污染（`en.wikipedia.org` 解析到 Facebook IP），连接超时。
- **Google / GitHub 搜索页（HTML）**：Google 被阻断；GitHub 仓库页可访问但搜索需登录。

实际可行通道（HTTP 200）：

- **Bing**（`www.bing.com/search`）：可获取结果，但 `<h2>` 标题需从 `b_algo` 块 + `<cite>` + `b_lineclamp` 段落解析（Bing 把结果 URL 包成 `ck/a?` 跳转）。
- **GitHub raw**（`raw.githubusercontent.com`）与 **GitHub API**（`api.github.com/repos/.../contents/...`）：可拉取规范原文与目录结构。
- **Baidu**：HTML 搜索会返回“百度安全验证”页，对 curl 不友好，未采用。

> Bash 工具默认沙箱无出站网络；上述抓取均以 `dangerouslyDisableSandbox: true` 执行。后续若需联网调研，沿用 Bing + GitHub raw 组合，或请用户以 `! <cmd>` 在会话内运行需代理的命令。

## 与 wiki 本体的关系

`upstream/` 里的文件**刻意不带 OKF frontmatter**——它们是上游规范的权威副本，加 frontmatter 会破坏其“逐字参考副本”语义。需要 OKF 合规的文档应放进 `wiki/`，而非这里。本目录是 meta-研究档案，可自由用普通 Markdown 撰写。
