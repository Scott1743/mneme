# Agent 驱动知识图谱构建 — 开源方案调研

> **日期**: 2026-07-20 · **研究目的**: 评估可用的开源知识图谱构建方案，为 Mneme v4.1 Graph Phase 2 提供技术选型
> **背景**: v4.0 Graph 的 `tagged_by` 关系占 99.5%(426/428)，拓扑退化为 tag hub 星形结构，G 阶段 nDCG@10 仅 0.486。需要引入 agent 辅助的实体/关系深度提取，让 Graph 真正有结构价值。

---

## TL;DR

**推荐方案**: **不引入重型框架，走"LLM API + 轻量 prompt 提取 + SQLite Graph 存储"的自建路径**

理由:
1. Mneme 的 Graph 已经有 SQLite 存储层和查询层，缺的只是"从文本提取更多实体关系"的构建层
2. 现有重型框架(GraphRAG / DeepKE / OpenSPG / LlamaIndex)都带完整的存储/查询/可视化栈，与 Mneme 的"disposable accelerator + OKF Markdown 真相源"设计哲学冲突
3. Mneme 本身就是 agent skill，dream 工作流里 agent 已经在读 Markdown 写概念页；让 agent 顺带提取实体关系，是最自然的扩展

**快速参考对比**:

| 方案 | 类型 | 中文支持 | 依赖 | 与 Mneme 适配度 |
|---|---|---|---|---|
| **自建 LLM Prompt 提取** | LLM 驱动 | ✅ 取决于模型 | 低(仅 LLM API) | ★★★★★ |
| DeepKE-LLM / OneKE | 深度学习 + LLM | ✅ 原生中文 | 中(torch + transformers) | ★★★☆☆ |
| LlamaIndex KnowledgeGraphIndex | LLM 框架 | ⚠️ 英文为主 | 中(llama-index + LLM API) | ★★★☆☆ |
| Microsoft GraphRAG | LLM 框架 | ⚠️ 英文为主 | 重(graphrag + blob storage) | ★★☆☆☆ |
| OpenSPG (蚂蚁+OpenKG) | 图谱引擎 | ✅ 原生中文 | 重(完整引擎栈) | ★☆☆☆☆ |
| spaCy + SpikeX | NLP 管道 | ❌ 中文弱 | 中(spaCy 模型) | ★★☆☆☆ |

---

## 1. 候选方案详评

### 1.1 自建 LLM Prompt 提取（推荐）

**核心思路**: 在 Mneme dream 工作流中，让 agent（或确定性 CLI 调用 LLM API）从每个 Markdown 页面提取：
- **实体**: 概念、产品、技术、人物、组织等（映射到 Graph 的 entity）
- **关系**: "A 使用 B"、"A 基于 B"、"A 与 B 相关"、"A 引用 B"等（映射到 Graph 的 relates_to）
- **属性**: 实体的关键属性（存入 properties JSON）

**优点**:
- 零额外依赖（Mneme 已经在 agent 环境里，LLM 调用走宿主 agent 的能力）
- 完全可控的输出格式（直接写入 SQLite Graph schema）
- 与 dream 工作流天然集成：agent 读页面写概念页时，顺便提取实体关系
- 支持中文（取决于用什么 LLM，国内模型都可以）
- 可渐进式：先从简单的"提取 5-10 个实体 + 3-5 个关系"开始，逐步优化 prompt

**缺点**:
- 需要自己设计 prompt 和输出 schema
- 提取质量依赖 LLM 能力，需要做验证和去重
- 没有内置的实体消歧(entity linking)

**技术要点**:
- 输出格式用 JSON Schema 约束，LLM 返回 `{"entities": [...], "relations": [...]}`
- 实体消歧：用 page 路径 + 实体名做唯一键，相似实体用 embedding 聚类合并
- 关系去重：(subject, predicate, object) 三元组做唯一键
- 与现有 Graph schema 对齐：entity_type 用 "concept"/"tool"/"person"/"org" 等，predicate 用 "relates_to"/"uses"/"based_on"/"references" 等

**与 Mneme 的集成点**:
- `reindex --graph --llm`：用 LLM 增强的 Graph 重建（显式 opt-in）
- dream 工作流：agent 写页后自动更新 Graph 中该页的实体和关系
- 持久化模式：类似 L2，成功执行一次 `reindex --graph --llm` 后进入 "Graph Phase 2 模式"

---

### 1.2 DeepKE / DeepKE-LLM（浙大）

**项目**: [zjunlp/DeepKE](https://github.com/zjunlp/DeepKE) · Star 数高 · EMNLP 2022

**定位**: 基于深度学习的中文知识抽取工具包，支持 NER、关系抽取、属性抽取。

**关键信息**:
- 有 **DeepKE-LLM** 版本，支持 LLM 驱动的知识提取（KnowLM / ChatGLM / LLaMA / GPT 等）
- 有 **OneKE** 框架（2024.4 发布），基于 Chinese-Alpaca-2-13B 的双语 IE 模型
- 支持低资源、少样本、文档级、多模态场景
- 2025.6 新增 MCP Tools 集成
- cnSchema 兼容（中文知识图谱 schema）

**优点**:
- ✅ 原生中文支持，有预训练中文模型
- ✅ 学术质量有保障（EMNLP 论文）
- ✅ 支持多种抽取任务（NER / RE / AE / Event）
- ⚠️ 有 LLM 版本，不需要自己写 prompt

**缺点**:
- ❌ 依赖重：PyTorch + Transformers，DeepKE-LLM 需要单独的 conda 环境
- ❌ 深度学习模型部署复杂，对硬件有要求（GPU 推荐）
- ❌ 输出格式需要适配 Mneme 的 SQLite Graph schema
- ❌ 项目更新频率下降（最新更新 2025.7，主要更新在 2022-2024）

**适配评估**:
- 如果用 **DeepKE-LLM** 的 API 调用方式，可以只取提取逻辑，不用它的存储层
- 但核心问题是：DeepKE 强在"训练和推理模型"，Mneme 缺的是"agent 工作流集成"，两者交集不大
- 如果要走深度学习路线，DeepKE 是中文首选，但 Mneme 的"零依赖/轻量"原则会被打破

---

### 1.3 LlamaIndex KnowledgeGraphIndex / PropertyGraphIndex

**项目**: [run-llama/llama_index](https://github.com/run-llama/llama_index) · 24.3k 依赖

**定位**: LLM 应用开发框架，内置多种索引类型，包括知识图谱索引。

**关键信息**:
- **KnowledgeGraphIndex**: 从文本构建实体关系三元组，基于 LLM 提取
- **PropertyGraphIndex** (更新): 向量 + 知识图谱的融合索引，支持属性图
- 支持多种图存储后端（Neo4j、NebulaGraph、Kuzu 等）
- 可插拔的 LLM / Embedding 提供商

**优点**:
- ✅ LLM 驱动，开箱即用
- ✅ 生态成熟，文档完善
- ✅ PropertyGraphIndex 是更先进的设计（属性图 + 向量混合）

**缺点**:
- ❌ 框架重：llama-index-core 本身有大量依赖
- ❌ 中文支持一般：文档和示例以英文为主，提取质量取决于所用 LLM
- ❌ 存储层与 Mneme 的 SQLite Graph 不兼容，需要桥接
- ❌ 设计哲学冲突：LlamaIndex 是"框架驱动"，Mneme 是"agent skill 驱动"

**适配评估**:
- 理论上可以只用 LlamaIndex 的抽取逻辑，输出对接 Mneme 的 SQLite Graph
- 但引入 llama-index-core 依赖太重，且抽取逻辑本身不复杂（就是调 LLM + 解析 JSON）
- 性价比：为了"实体关系提取"这一个功能引入整个 LlamaIndex 框架，不值得

---

### 1.4 Microsoft GraphRAG

**项目**: [microsoft/graphrag](https://github.com/microsoft/graphrag) · 10.8k stars · v3.1.0

**定位**: 微软研究院的 GraphRAG 系统，从非结构化文本提取结构化数据并构建图谱用于 RAG。

**关键信息**:
- 完整的 end-to-end 管道：索引 + 查询 + 可视化
- 基于 LLM 的社区检测、层次化图谱
- 支持全局搜索（社区级摘要）和局部搜索（实体级）
- 有 Arxiv 论文：https://arxiv.org/pdf/2404.16130

**优点**:
- ✅ 工业级质量，微软研究院出品
- ✅ 完整的 GraphRAG 方法论（不仅仅是提取）
- ✅ 社区检测和层次化是亮点

**缺点**:
- ❌ 非常重：完整的 data pipeline + blob storage + 多种 LLM 调用
- ❌ 英文为主，中文需要自行适配 prompt
- ❌ 设计目标是"企业级 RAG 系统"，不是"给 wiki 加个图谱索引"
- ❌ 与 Mneme 的 "Markdown 真相源 + disposable accelerator" 设计哲学完全不同

**适配评估**:
- GraphRAG 是完整的产品级系统，Mneme 只需要它的"实体关系提取"这一环
- 直接用 GraphRAG 等于把 Mneme 变成 GraphRAG 的前端，得不偿失
- 但 **GraphRAG 的 prompt 设计和社区检测算法值得参考**

---

### 1.5 OpenSPG（蚂蚁集团 + OpenKG）

**项目**: [OpenSPG/openspg](https://github.com/OpenSPG/openspg) · Apache 2.0

**定位**: 基于 SPG（Semantic-enhanced Programmable Graph）框架的知识图谱引擎。

**关键信息**:
- 蚂蚁集团多年金融领域知识图谱经验的沉淀
- SPG-Schema 语义建模、SPG-Builder 知识构建、SPG-Reasoner 规则推理
- 支持非结构化知识构建（结合 NLP/深度学习）
- KNext 可编程框架，支持 LLM 和图学习接入

**优点**:
- ✅ 原生中文支持，中文社区活跃
- ✅ 工业级质量，金融场景验证
- ✅ 完整的图谱构建 + 推理能力

**缺点**:
- ❌ 极重：完整的知识图谱引擎栈，需要部署多个组件
- ❌ 学习曲线陡峭：SPG 框架、Schema 设计、KGDSL 等
- ❌ 与 Mneme 的"轻量 disposable"定位完全不符
- ❌ 存储层完全不同，无法对接

**适配评估**:
- OpenSPG 是"建一座完整的知识图谱工厂"，Mneme 是"给 wiki 加个图谱索引"
- 完全不是一个量级的东西，不适合

---

### 1.6 spaCy + SpikeX

**项目**: spaCy 生态 + SpikeX 插件

**定位**: 工业级 NLP 库 + 知识提取管道组件。

**关键信息**:
- spaCy: 工业级 NLP，有 NER、依赖解析等
- SpikeX: spaCy 的知识提取自定义管道组件集合
- 支持实体链接、关系抽取、概念提取

**优点**:
- ✅ 速度快，性能好
- ✅ 成熟稳定

**缺点**:
- ❌ 中文支持弱：spaCy 的中文模型质量不如英文
- ❌ 关系抽取需要自定义模型或规则
- ❌ 不是 LLM 驱动，提取质量有上限
- ❌ 需要训练数据或规则

**适配评估**:
- 中文场景下不推荐
- 如果以后需要英文 wiki，可以考虑作为快速 baseline

---

## 2. 推荐方案详解：自建 LLM Prompt 提取

### 2.1 为什么自建

1. **Mneme 已经有 agent**：dream 工作流里 agent 就在读 Markdown、写概念页、加 tags 和 links。让 agent 顺带提取实体关系，是最自然的扩展。
2. **Graph 存储层已经有了**：SQLite Graph schema 已定义，查询层（BFS + hybrid search）已实现，缺的只是"填数据"。
3. **零额外依赖**：LLM 调用走宿主 agent 的能力，不需要加 PyTorch / 图数据库 / 重型框架。
4. **完全可控**：prompt 可以针对 Mneme 的 OKF 概念页特点优化，输出格式直接对齐 Graph schema。
5. **渐进式路线**：先从简单提取开始，逐步迭代，每一步都可以验证效果。

### 2.2 技术架构

```
OKF Markdown 页面
      │
      ▼
  LLM 提取 Prompt
  (JSON Schema 约束)
      │
      ▼
  ┌─────────────────┐
  │  entities[]     │ ──▶  去重 / 消歧  ──▶  SQLite Graph entities 表
  │  relations[]    │ ──▶  去重 / 验证  ──▶  SQLite Graph relations 表
  └─────────────────┘
      │
      ▼
  Graph 质量检查
  (连通分量 / 孤立实体 / 关系类型分布)
```

### 2.3 Prompt 设计（初版）

**输入**: 一个 OKF 概念页的 frontmatter + 正文（截断到合适长度，如前 2000 字）

**输出**:
```json
{
  "entities": [
    {
      "name": "实体名称",
      "type": "concept|tool|person|org|product|technology",
      "description": "一句话描述",
      "confidence": 0.9
    }
  ],
  "relations": [
    {
      "subject": "主体实体名",
      "predicate": "relates_to|uses|based_on|references|part_of|alternative_to",
      "object": "客体实体名",
      "confidence": 0.85,
      "evidence": "原文中支撑这个关系的句子"
    }
  ]
}
```

### 2.4 实体消歧与去重

1. **页面内去重**: 同一页面内同名实体合并
2. **跨页面消歧**:
   - 实体名完全相同 → 合并
   - 实体名相似（embedding 相似度 > 阈值）→ 提示 agent 确认是否合并
   - 用实体 description 辅助判断
3. **与现有 Graph 实体合并**:
   - 按 name + entity_type 做唯一键
   - 已存在的实体更新 description，不重复插入

### 2.5 与现有 Graph 的关系

**保留现有结构**:
- `tagged_by` 关系继续从 frontmatter tags 派生
- `relates_to` 关系继续从 Markdown 链接派生
- 新增的 LLM 提取实体和关系作为补充

**扩展 Graph schema**:
- entities 表新增 `source` 字段：`"markdown_link"` / `"tag"` / `"llm_extracted"`
- entities 表新增 `confidence` 字段：0-1 置信度
- relations 表新增 `source` / `confidence` / `evidence` 字段
- 支持按 source 和 confidence 过滤

### 2.6 Phase 2 路线图

| 阶段 | 内容 | 产出 |
|---|---|---|
| Phase 2.1 | LLM 提取实体关系的 CLI 子命令 `reindex --graph --llm` | 可从命令行触发的图谱增强 |
| Phase 2.2 | SKILL.md 中 dream 工作流加入 Graph 提取引导 | agent dream 时自动提取实体关系 |
| Phase 2.3 | 实体消歧与合并算法 | 跨页面的实体统一 |
| Phase 2.4 | 社区检测算法（如 Leiden） | 自动发现主题社区，辅助 search |
| Phase 2.5 | entity embedding + 混合检索 | Graph 搜索支持语义相似度 |

---

## 3. 风险与挑战

### 3.1 LLM 成本
- 每个页面一次 LLM 调用，142 页大约... 根据页面长度和模型价格而定
- 缓解：只在 dream 时增量提取（新建/修改的页面才提取），不是全量重建
- 缓解：用小模型（如 7B 本地模型或轻量 API）

### 3.2 提取质量
- LLM 可能提取出不准确的实体或关系
- 缓解：保留 confidence 字段，低置信度的可以标记为待审核
- 缓解：evidence 字段记录原文依据，便于验证
- 缓解：agent dream 流程中提取的内容默认进入"预览"状态，用户确认后写入

### 3.3 实体消歧
- 不同页面提到的同一实体可能用不同名字
- 缓解：先用简单规则（完全匹配），再用 embedding 相似度辅助
- 缓解：Phase 2 后期再做消歧，前期接受一定的实体冗余

### 3.4 与 OKF 原则的冲突
- Graph 是 disposable accelerator，不能让 LLM 提取的内容反向写入 Markdown 正文
- 缓解：LLM 提取只进 Graph（disposable），不碰 Markdown 真相源
- 缓解：如果提取结果很好，agent 可以建议用户手动把重要关系写成 Markdown 链接，但不自动改

---

## 4. 结论

| 方案 | 推荐度 | 说明 |
|---|---|---|
| **自建 LLM Prompt 提取** | ★★★★★ | 最符合 Mneme 设计哲学，与 dream 工作流天然集成 |
| DeepKE-LLM | ★★★☆☆ | 中文首选深度学习方案，但依赖重，适合有 GPU 的场景 |
| LlamaIndex KG Index | ★★★☆☆ | 框架太重，提取逻辑本身不难，不值得引入 |
| Microsoft GraphRAG | ★★☆☆☆ | 完整系统，不是"组件"，设计哲学不匹配 |
| OpenSPG | ★☆☆☆☆ | 量级完全不同，不适合 |
| spaCy + SpikeX | ★★☆☆☆ | 中文弱，非 LLM 驱动，上限低 |

**下一步行动**:
1. 设计 LLM 提取 prompt 和输出 schema
2. 在 `reindex --graph --llm` 中实现第一版提取
3. 用佳都飞书文档库做测试，对比 G 阶段 nDCG 提升
4. 验证可行后再集成到 SKILL.md dream 工作流
