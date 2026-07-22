# Mneme Web UI（`mneme serve`）设计原型

> **状态**：P1 + Graph 工作台已实施 · 2026-07-22
> **配套**：可交互静态原型 [webserver-mock.html](./webserver-mock.html)（浏览器直接打开，无需启动任何服务）

## 0. 一句话

给 skill 增加一个 `mneme serve` 子命令：**用户显式启动、前台运行、Ctrl-C 即停、只绑 localhost** 的 stdlib 零依赖 Web 控制台，把 `lint / search / dream / reindex` 的能力变成一座可视化面板。

## 1. 背景与目标

当前 mneme 的全部交互都发生在「用户 ↔ agent ↔ CLI」链路里。对**不使用 agent、只想自己看 wiki 健康状况、搜一搜、浏览一下**的用户，缺一个直观的入口。目标：

1. **可视化体检**：lint 诊断、orphans、索引新鲜度一屏看清，而不是读文本日志。
2. **可视化搜索与浏览**：搜索候选点击直达页面，页面间链接可点击跳转。
3. **可视化 dream 审计**：审计报告图形化呈现；写侧仍走 preview → 用户点头 → 写盘的审批契约，Web 只是换一种"点头"的方式。
4. **零学习成本**：`mneme serve` 回车 → 浏览器打开 → 用完 Ctrl-C。

## 2. 与项目宪法的张力与调和（必须先讲清楚）

| 宪法条款 | 表面冲突 | 调和方案 |
|---|---|---|
| **按需、无自建常驻服务** | HTTP server 是个常驻进程 | `serve` 是**用户显式拉起的前台进程**，与 `python -m http.server`（仓库已有先例，introduction 预览）同类：不注册 launchd/systemd、不开机自启、不 fork daemon、不写 pidfile。进程生命周期完全由用户终端控制。宪法禁止的是"常驻基础设施"，不是"用户手里的临时工具"。 |
| **stdlib 零依赖**（test_zero_dep.py 强制） | flask/fastapi 全部出局 | 服务端只用 `http.server.ThreadingHTTPServer` + `json` + `urllib`；前端**零 CDN、零 npm**——单个自包含 HTML + 原生 ES2017 JS + 手写 CSS，随 skill zip 分发。中国网络受限环境下也能离线工作。 |
| **dream 默认 preview-only** | Web 有按钮，按钮会写盘 | P1 **完全只读 + 可重建的 disposable 缓存**（reindex 允许，因为它只重建 `.mneme/` 下可删缓存，不是事实）。任何写事实正文的操作（dream 落盘）推迟到 P2，且必须完整复刻「预览 → 差异展示 → 用户显式确认」三段式，服务端无确认 token 拒绝写入。 |
| **disposable accelerator** | server 算不算新的状态持有者 | server **无状态**：不存任何自有数据库；每次请求直接读 bundle 与 `.mneme/` 现有 db。删掉 server 代码，wiki 一个字节不少。 |
| **MCP 暂不实现** | 这是不是变相做 server | 不是。MCP 是"跨客户端一等工具协议"，本设计是"单用户本地面板"，不实现 MCP 协议、不暴露给 agent 网络调用。MCP 仍按原 deferred 决策等待真实触发条件。 |

## 3. 总体架构

```
用户终端                    本机 127.0.0.1:8620
┌──────────────┐   启动   ┌─────────────────────────────────┐
│ mneme serve  │ ──────►  │ ThreadingHTTPServer (stdlib)    │
│  (前台进程)   │ ◄──────  │  ├─ GET  /            → 内嵌 UI │
└──────────────┘  Ctrl-C  │  ├─ GET  /api/status  → JSON   │
                          │  ├─ GET  /api/search?q=→ JSON   │
浏览器 (用户手动打开       │  ├─ GET  /api/page?path=→ JSON  │
 或 --open 自动打开)      │  ├─ GET  /api/lint    → JSON    │
                          │  ├─ GET  /api/dream   → JSON    │
                          │  └─ POST /api/reindex → JSON    │
                          └───────┬─────────────────────────┘
                                  │ 直接 import（非 subprocess）
        ┌─────────────────────────┼──────────────────────────┐
        ▼                         ▼                          ▼
  okflib.lint_bundle      indexlib/graphlib.search      dream.dream_audit
  tools_helpers.resolve_bundle     config.load_config
        │                         │                          │
        └─────────── 只读访问 bundle + .mneme/{fts,graph,l2}.db ──┘
```

**关键决策**：

1. **内嵌调用，不走 subprocess**。`cli.main(argv)` 与各 lib 模块本就是惰性 import，server 直接 `from .dream import dream_audit` 等，零进程开销、错误即 Python 异常，好处理。
2. **lint 无需补 `--json`**。`okflib.lint_bundle()` 返回的本来就是结构化诊断对象，`cmd_lint` 只是把它格式化成文本；server 直接序列化底层对象，不解析文本输出。
3. **UI 单文件内嵌**。整个前端是 `webui.py` 里一个 `INDEX_HTML` 字符串（HTML+CSS+JS 一体，约 1500 行内），`GET /` 直接返回。好处：zip 打包零新增文件类型、无路径问题、无静态目录安全面；坏处：不利于前端工程化——P1 接受这个代价。
4. **Markdown 渲染用极简前端渲染器**（约 100 行 JS：标题/列表/加粗/行内代码/代码块/链接）。明确标注为"近似渲染"，不做完整 CommonMark——**权威永远是 Markdown 源**，页面同时提供「源」/「渲染」切换。

**新增代码落点**（全部在交付物 `skills/mneme/` 内）：

```
skills/mneme/scripts/mneme/
├── cli.py              # build_parser() 增加 serve 子命令（~15 行）
├── webserver.py        # HTTP handler + 路由 + API 序列化（~400 行）
└── webui.py            # INDEX_HTML 内嵌单页应用（前端全量）
```

## 4. CLI 接口设计

```
mneme serve [--bundle PATH] [--config PATH]
            [--host 127.0.0.1] [--port 8620] [--open]
```

- `--host`：默认 `127.0.0.1`。**显式传 `0.0.0.0` 才允许局域网访问**，启动时打印一次醒目警告。
- `--port`：默认 `8620`；传 `0` 随机端口（避免冲突场景）。
- `--open`：启动后 `webbrowser.open()`。
- bundle 解析沿用冻结优先级：`--bundle` > `$MNEME_BUNDLE` > config.toml > cwd 祖先 > `./wiki`。
- 启动时若 bundle 未初始化（无 `index.md`），UI 进入"空 bundle"引导页而非报错退出。

## 5. HTTP API 设计

全部端点只接受 `GET`（读）与少数 `POST`（写缓存/写事实），JSON UTF-8。错误统一 `{"error": "...", "code": "..."}` + 合适 HTTP 状态码。

| 端点 | 方法 | 语义 | 数据来源 |
|---|---|---|---|
| `/api/status` | GET | bundle 路径、版本、概念页计数、索引三件套存在性与新鲜度、lint 错误/警告计数、log.md 最近 5 条 | okflib + graphlib + indexlib + config |
| `/api/lint` | GET | 完整诊断列表 `{severity, path, rule, detail}` + orphans | `okflib.lint_bundle` |
| `/api/search?q=&k=&mode=` | GET | 候选列表 `{path, title, snippet, score}`；mode 默认沿用 CLI 决策链 | indexlib/graphlib |
| `/api/pages?type=&tag=` | GET | 页面清单（frontmatter 摘要），支持按 type/tag 过滤 | okflib 扫描 |
| `/api/page?path=` | GET | 单页：frontmatter dict + raw markdown + 出链/入链 + Graph 上下文 | 文件 + graphlib |
| `/api/dream` | GET | dream 只读审计报告（hard rules / writer rules / graph 健康） | `dream.dream_audit` |
| `/api/graph` | GET | 两层节点/关系、来源页、证据、置信度与健康统计 | graphlib |
| `/api/reindex` | POST | 首次创建或重建 FTS5/Graph 缓存（disposable，幂等） | `cmd_reindex` 同款逻辑 |

**写侧（仅 P2，且需确认 token）**：

| 端点 | 方法 | 语义 |
|---|---|---|
| `/api/dream/preview` | POST | 提交 source 内容 → 返回计划变更清单（新增/修改文件 + diff）+ 一次性 `confirm_token`（5 分钟过期） |
| `/api/dream/apply` | POST | 带 `confirm_token` 才执行写盘；token 一次性作废。无 token / 过期 / 内容变动 → 409 拒绝 |

## 6. 页面与交互原型

单页应用，顶部 6 个 Tab。完整可点版本见 [webserver-mock.html](./webserver-mock.html)，此处为结构草图。

### 6.1 总览（默认页）

```
┌ Mneme ──────────────────────── bundle: ~/wiki ─┐
│ [总览] 搜索  浏览  体检  Dream  图谱            │
├────────────────────────────────────────────────┤
│  ◆ 健康度  ✓ 0 ERROR · 3 WARN        [重新体检] │
│  ◆ 页面    42 概念 · 12 引用 · 5 主题           │
│  ◆ 索引    FTS5 ✓  Graph ✓(新鲜)  L2 ✗ 未启用  │
│            [重建索引]                           │
│  ◆ 最近动态（log.md 尾部 5 条）                  │
│    2026-07-20 dream | OKF 协议概念页补充         │
│    ...                                          │
└────────────────────────────────────────────────┘
```

### 6.2 搜索

左侧 query 框 + mode 下拉（auto/fts/hybrid/l2）+ type 过滤；右侧结果卡片（标题、路径、snippet 高亮），点击卡片 → 跳到浏览页对应页面。**只读**，与 SKILL.md「search 永不写」一致。

### 6.3 浏览

左栏目录树（按目录分组，可按 type/tag 过滤，orphan 页面单独一组标灰）；右栏页面渲染，支持「渲染 / 源」切换；正文中的 bundle 链接可点击跳页；页面底部列出**出链与入链**（来自 graph.db）。

### 6.4 体检

诊断表格：severity 徽标 / rule / 路径（点击跳浏览页）/ detail；顶部按 rule 聚合的统计条；orphans 独立卡片。「重建索引」按钮复用 `/api/reindex`。

**一键复制修复提示词（P1）**：每行诊断尾部一个「复制修复提示词」按钮，顶部另有「复制全部诊断」按钮。点击后在面板内弹出预览框，展示组装好的提示词全文，用户确认后一键复制（`navigator.clipboard`，带降级 `textarea` 方案），粘贴给 agent 即进入正式修复流程。提示词在**前端用 `/api/lint` 返回的结构化诊断现场组装**（不新增 API），模板包含：

- bundle 绝对路径与该条/全部诊断的 `severity / rule / path / detail`；
- 涉及的规则出处（OKF SPEC 条款号或 mneme 写作纪律条目）；
- 硬约束提醒：不碰 raw sources、写入前先预览并等待用户确认、改动需同步 `index.md` / `log.md`；
- 建议的验收方式（修复后重跑 `mneme lint`）。

与「发起 dream」按钮同一设计模式：**面板不自己修，把结构化上下文组装好交给 agent**——零写盘风险。

### 6.5 Dream（按钮触发的三层模型）

**关键事实**：`mneme dream` CLI 本身是**只读审计**；真正的 dream 写盘（读 source、蒸馏成概念页、互链、更新 index/log）是 agent 按 SKILL.md 工作流做的语义工作，CLI 与 webserver 都没有这个智能。因此"按钮触发 dream"必须拆成三层，按钮是**发起入口与审批入口，不是执行者**：

| 按钮 | 触发什么 | 期 | 约束 |
|---|---|---|---|
| **重新审计** | 重跑 `dream.dream_audit()` 刷新报告 | P1 | 纯只读，无约束问题 |
| **发起 dream** | 唤起宿主 agent 执行 dream 工作流（读 source → 蒸馏 → 产出预览），完成后回面板等待确认 | P2 | 需宿主集成（Kimi Work 里是一个 widget task / cron job 的 run；Claude Code 里是一次会话任务）。独立 stdlib server 无宿主连接时，按钮降级为"生成一段可粘贴给 agent 的 dream 指令文本" |
| **确认写入** | 对预览中已列明的变更执行落盘 | P2 | 带一次性 confirm token；无 token / 过期 / 内容变动 → 409 拒绝。审批契约不变，确认动作从"对话里点头"变成"看完 diff 点按钮" |

**P1 形态**：只读审计报告可视化——okf_hard_rules 与 mneme_writer_rules 各项打勾/打叉，graph 健康摘要，「重新审计」按钮；顶部横幅写清"本面板不执行写盘；写入请在 agent 会话中完成 dream 审批流"。

**P2 形态**（需另行批准）：拖入 source 文件 / 点「发起 dream」→ 宿主 agent 产出预览 → 面板展示变更 diff → 「确认写入」按钮（带二次确认弹窗，显示将改动的文件清单）。蒸馏计划永远由 agent 产出，webserver 只存"待确认计划"并执行被确认的那一份，绝不现场做语义蒸馏。

### 6.6 图谱（P3）

graph.db 的节点/边用原生 Canvas 力导向布局渲染，无第三方图库。工作台可按基础层/富化层、节点种类、关系谓词和关键词切片；页面、标签和 agent 实体采用不同形状。选中节点或关系会显示邻接关系、置信度、证据与来源页面，浏览页也反向显示当前页面的 Graph 上下文。Graph 缺失时明确提示首次构建，富化层为空时不会伪装成已有数据。

## 7. 安全模型

1. **默认只绑 `127.0.0.1`**；绑 `0.0.0.0` 需显式 `--host`，启动打印警告。
2. **启动时生成随机 session token**（打印在终端，同时注入 `GET /` 返回的页面）；所有 `/api/*` 与 POST 要求 `X-Mneme-Token` 头匹配——防止同机其他进程/恶意网页跨站调用（DNS rebinding 层面靠 Host 头校验辅助）。
3. **路径沙箱**：`/api/page?path=` 等一律经 `resolve` 后校验仍在 bundle 内，拒绝 `..` 逃逸与绝对路径。
4. **请求体上限** 1 MB；无文件上传（P2 dream preview 也只接受文本/JSON body）。
5. **不 set-cookie、不存 localStorage**——token 只活在内存里，关页即失效。
6. 读请求天然幂等；写请求仅 `/api/reindex`（disposable）与 P2 的 token 化 dream apply。

## 8. 对既有冻结测试与打包的影响

- `test_zero_dep.py`：`webserver.py` / `webui.py` 加入 AST 扫描白名单对象（它们也只 import stdlib，理论上白名单不用改，但新增文件需纳入扫描范围验证）。
- `test_skill_text.py` / `test_skill_drift.py`：SKILL.md 需新增一小节「可视化面板（可选）」，说明 `mneme serve` 的存在与只读边界——文本冻结测试同步更新。
- `test_release_layout.py` / `test_zip_builder.py`：确认新增两个 `.py` 进入 zip 布局断言。
- 新增 `tests/test_webserver.py`：起 ephemeral 端口实例，覆盖 status/lint/search/page 的路径沙箱与 token 校验。
- 版本号：进 `[Unreleased]` → 下个 minor（4.2.0），`__init__.py` 与 SKILL.md frontmatter 同步。

## 9. 分期路线

| 期 | 内容 | 写盘能力 |
|---|---|---|
| **P1（本原型对应）** | serve 子命令 + 总览/搜索/浏览/体检/Dream 审计只读 + reindex 按钮 | 仅 disposable 缓存重建 |
| **P2** | dream preview → diff → token 化确认写盘；页面 frontmatter 在线编辑（同样走 preview+confirm） | 事实写入，完整复刻审批契约 |
| **P3（Graph 已实施）** | 两层图谱力导向可视化、证据/来源页与切片；log.md 时间线和局域网分享仍按需 | 仅 disposable 缓存重建 |

P1 不依赖 P2；P2 每一个写入端点单独评审。任何一期都不引入第三方依赖、不引入构建步骤。

## 10. 非目标

- 不做 MCP server、不实现任何远程访问/多用户/账号体系。
- 不做完整 CommonMark 渲染、不做所见即所得编辑器（权威是 Markdown 源）。
- 不做自动刷新/文件监听热重载（P1 手动点"重新体检"；watchdog 类依赖永远出局）。
- 不替代 agent 的 dream 综合判断：Web 的 P2 写盘只执行**已经在预览里明确列出**的变更，不现场做语义蒸馏。
- 不做移动端适配的极致优化（响应式可用即可）。
- **不引入诊断存储表**。诊断是派生数据，bundle 是唯一事实源，lint 随时可从 Markdown 重算（本地扫描，毫秒级），请求时实时计算即可；存表等于制造第二个会腐化的事实源，违背 disposable accelerator 哲学。若未来想要"健康度趋势"，只允许用可删除的 append-only 快照文件（如 `.mneme/health-history.jsonl`），永远不当权威、可整体删除。

## 11. 待核对的开放问题

1. **写侧边界**：P1 纯只读（含 reindex + 「重新审计」按钮）是否就是你想要的？还是希望 P1 就带 dream 审批写盘？（建议：先只读上线，写盘单独立项评审。）
2. **「发起 dream」按钮的宿主形态**：按钮唤起 agent 这件事，在 Kimi Work 里可以落成 widget task / cron job 的一次 run；但 skill 也分发给无宿主集成的环境（独立 stdlib server），那里按钮只能降级为"生成 dream 指令文本"。接受这种双态降级，还是「发起 dream」干脆标注为"仅宿主集成环境可用"？
3. **UI 形态**：接受"单文件内嵌 HTML 字符串"（零构建、zip 友好）还是更愿意 `webui/` 静态目录（好维护，多几个文件）？
4. **默认端口 8620** 是否顺手？是否要 `--open` 默认开启？
5. **图谱页（已解决）**：已实现基础/富化切片、证据、来源页和页面反向 Graph 上下文。
6. 这个面板与 agent 的关系定位：纯"人类自助工具"，还是未来也要成为 agent 夜巡报告的可视化出口（那会影响 dream 页设计）？
