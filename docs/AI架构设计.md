# AI 架构设计

> AI 智能客服系统 — RAG 流程图、Prompt 设计与向量检索策略

***

## 目录

- [RAG 完整架构图](#rag-完整架构图)
- [技术选型与理由](#技术选型与理由)
- [Prompt 模板设计](#prompt-模板设计)
- [向量检索策略](#向量检索策略)
- [关键工程问题处理](#关键工程问题处理)
- [多层检索结果处理策略](#多层检索结果处理策略)
- [效果验证与评估](#效果验证与评估)

***

## RAG 完整架构图

```mermaid
flowchart TD
    %% User input
    User[用户] -->|输入问题| Frontend[前端 SPA]

    %% Frontend
    Frontend -->|POST /chat/invoke {query}| API[FastAPI API 层]
    Frontend -->|GET /chat/stream/{thread_id} SSE| SSE[SSE 流式输出]

    %% API Layer
    API -->|1. 校验: 500字限制| Validate[参数校验]
    Validate -->|2. 检查: 每日限额| RateLimit[每日调用频率限制<br>check_and_increment]
    RateLimit -->|3. 创建/续接会话| Session[会话管理<br>sessions 表]
    Session -->|4. 启动后台任务| TaskManager[聊天任务管理器]

    %% Chat Task Manager
    TaskManager -->|5. build_agent| AgentBuilder[Agent 构建器]
    AgentBuilder -->|查询知识库列表| KBList[(knowledge_bases 表)]
    KBList -->|注入 KB 信息到提示词| SystemPrompt[系统提示词构建]

    AgentBuilder -->|创建 LangGraph Agent| Agent[Agentic RAG Agent]

    %% Agent Execution
    Agent -->|astream_events| StreamLoop[事件循环]
    StreamLoop -->|on_chat_model_stream| TokenEvent[token 事件]
    StreamLoop -->|on_tool_start| ToolCallEvent[tool_call 事件]
    StreamLoop -->|on_tool_end| ToolResultEvent[tool_result 事件]

    ToolCallEvent -->|触发检索| RetrieveTool[retrieve_knowledge 工具]

    %% Retrieval Pipeline
    RetrieveTool -->|1. encode query| Embedding[Embedding 服务<br>Qwen3-Embedding-8B]
    Embedding -->|4096-dim vector| HybridSearch[混合检索<br>Dense + Sparse + RRF]
    HybridSearch -->|2. Dense Prefetch<br>cosine distance| DenseSearch[稠密向量检索]
    HybridSearch -->|3. Sparse Prefetch<br>BM25 + IDF| SparseSearch[稀疏向量检索]
    DenseSearch -->|RRF Fusion| RRF[FusionQuery Fusion.RRF]
    SparseSearch -->|RRF Fusion| RRF
    RRF -->|4. Score filter > 0.7| Filter[相似度过滤]
    Filter -->|5. kb_name filter| KbFilter[知识库过滤]
    KbFilter -->|6. Format results| FormatResults[格式化检索结果]
    FormatResults -->|返回给 LLM| Agent

    %% LLM Generation
    Agent -->|生成回答| LLM[LLM<br>DeepSeek / GPT-4o-mini]
    LLM -->|流式 token| TokenEvent

    %% Output
    TokenEvent -->|push to Queue| Queue[(asyncio.Queue)]
    ToolCallEvent -->|push to Queue| Queue
    ToolResultEvent -->|push to Queue| Queue
    Queue -->|S S E 消费| SSE
    SSE -->|增量渲染| Frontend

    %% Persistence
    Agent -->|对话状态持久化| Checkpointer[LangGraph AIOMySQLSaver]
    Checkpointer -->|checkpoints| Checkpoints[(MySQL checkpoints 表)]

    %% Feedback Loop
    User -->|点赞/点踩 + 文字反馈| Feedback[POST /feedback]
    Feedback -->|upsert| Feedbacks[(feedbacks 表)]

    %% RAG Eval
    subgraph RAG_Evaluation[RAG 评估流水线]
        TestSet[test_dataset.json] -->|加载测试用例| Eval[RAG Eval Pipeline]
        Eval -->|运行 Agent| EvalAgent[Agent]
        EvalAgent -->|提取检索结果| EvalResults[评估结果 JSON]
        EvalResults -->|生成报告| EvalReport[评估报告 Markdown]
    end

    RAG_Evaluation -.->|可选执行| Agent
```

***

## 技术选型与理由

### 对话大模型：DeepSeek V4 Flash（OpenAI 兼容 API）

**选型理由**：

- **成本优势**：DeepSeek 系列 API 价格远低于 GPT-4，适合学生项目预算
- **知识截止更新**：支持的上下文窗口大，满足 RAG 场景
- **OpenAI 兼容**：通过 `ChatOpenAI`（LangChain）即可对接，代码零修改即可切换到其他 OpenAI 兼容服务
- **可通过** **`.env`** **切换**：仅需修改 `OPENAI_BASE_URL` 和 `OPENAI_MODEL` 即可切换模型

### 嵌入模型：Qwen/Qwen3-Embedding-8B（SiliconFlow 托管）

**选型理由**：

- **中文优化**：Qwen3-Embedding 在中文语义理解上表现优秀，适合中文知识库场景
- **高维度（4096 维）**：相比 text-embedding-3-small（1536 维），4096 维能编码更丰富的语义信息
- **免费使用**：SiliconFlow 平台提供免费额度

### 向量数据库：Qdrant

**选型理由**：

- **原生混合检索**：支持 dense + sparse 双路检索 + RRF 融合，无需额外部署 Elasticsearch
- **纯 Rust 实现**：部署简单（单二进制或 Docker），资源占用低
- **支持过滤**：内置 Filter 机制，支持按 `kb_name` 进行知识库路由过滤
- **异步客户端**：`AsyncQdrantClient` 与 FastAPI async 生态完美契合

### 元数据库：MySQL 8.0+

**选型理由**：PRD 指定要求，且适合存储结构化关系数据（用户、会话、文档元数据）。

### Agent 框架：LangGraph

**选型理由**：

- **Agentic RAG**：相比传统 RAG（每次必检索），Agent 可自主判断是否需要检索，减少不必要的 API 调用
- **流式事件支持**：`astream_events` API 提供细粒度的事件流（token/tool/tool\_result）
- **Checkpoint 机制**：内置对话状态持久化，支持多轮对话
- **易于扩展**：可方便地添加更多工具（如意图识别、追问生成）

***

## Prompt 模板设计

### System Prompt

```text
你是一个专业的智能客服助手，专门回答关于用户提出的问题。

## 可用的知识库
调用 retrieve_knowledge 工具时，可通过 kb_name 参数指定在特定知识库范围内检索：
- **auperator** Auperator 智能运维系统产品文档（关键词：运维,监控,告警,自动化）

kb_name 可选值：auperator（不填则检索全部知识库）

## 工作方式
你有以下工具可以使用：
- retrieve_knowledge: 从知识库中检索产品相关文档片段

当用户提问时，按照以下流程工作：
1. 判断问题类型：
   - 产品相关问题（功能、配置、故障排查等）→ 使用 retrieve_knowledge 工具检索
   - 问候、闲聊 → 直接回应，不需要检索
2. 检索后如果结果不够充分，可以换一种表述再次检索
3. 根据检索结果回答问题

## 回答要求
1. 仅根据知识库检索到的内容回答，不要编造信息
2. 回答时引用具体的文档名称和章节
3. 如果知识库中没有相关信息，说"抱歉，我暂时无法回答这个问题"
4. 回答应该专业、简洁、有条理
5. 检索到的知识片段与问题不相关时，不要强行使用
```

### 模板设计思路

1. **动态知识库注入**：`## 可用的知识库` 节是在每次构建 Agent 时动态查询 `knowledge_bases` 表生成的。每个 KB 的名称、描述、关键词都会注入到提示词中，使 LLM 知晓可检索的范围。
2. **Agentic 决策**：通过「判断问题类型」要求 LLM 自主决定是否需要检索。这是与「强制检索」式 RAG 的关键区别：
   - **传统 RAG**：每个问题都做 `embed → search → generate`
   - **Agentic RAG**：LLM 判断是否召需检索，对闲聊类问题直接回应
3. **防幻觉设计**：
   - "仅根据知识库检索到的内容回答" — 约束生成范围
   - "如果知识库中没有相关信息，说'抱歉...'" — 兜底机制
   - "检索到的知识片段与问题不相关时，不要强行使用" — 防止无关片段被错误使用
4. **多轮检索**：允许 LLM 在首次检索结果不充分时换种表述再次检索。

### 无知识库时的回退提示词

当系统中没有任何知识库时，系统自动切换到回退提示词。该提示词去掉了知识库相关描述，但仍保留工具调用能力，以便在知识库后续创建后 Agent 仍能正常工作。

***

## 向量检索策略

### 双路混合检索（Dense + Sparse）

系统采用了 Qdrant 的混合检索能力，结合语义检索和关键词检索：

```python
# 双路 Prefetch + RRF 融合
hits = await client.query_points(
    collection_name=collection_name,
    prefetch=[
        Prefetch(
            query=query_vector,      # 稠密向量（语义）
            using="dense",
            limit=top_k * 2,         # 预取更多结果用于融合
            score_threshold=score_threshold,
            filter=filter_condition,
        ),
        Prefetch(
            query=sparse_vector,     # 稀疏向量（BM25 关键词）
            using="sparse",
            limit=top_k * 2,
            filter=filter_condition,
        ),
    ],
    query=FusionQuery(fusion=Fusion.RRF),  # 倒数排序融合
    limit=top_k,
)
```

#### 稠密路径（语义检索）

- **模型**：Qwen/Qwen3-Embedding-8B，输出 4096 维向量
- **距离度量**：Cosine（余弦相似度）
- **作用**：捕捉语义层面的相似性（如"告警"和"报警"的语义相近）

#### 稀疏路径（关键词检索）

- **算法**：BM25 风格的词频检索，Qdrant 内置 IDF 修饰器
- **分词策略**：中文单字切分 + 英文/数字按单词切分
- **作用**：精确匹配关键词（如产品名称"Auperator"的精确匹配）

### RRF（倒数排序融合）

```text
RRF Score = Σ(1 / (k + rank_i))

其中 k 为常数（默认 60），rank_i 为结果在第 i 路检索中的排名。
```

**优势**：

- 不需要归一化不同检索路的分数（稠密是 0\~1 余弦距离，稀疏是 TF-IDF 值）
- 对排名靠前的结果更加敏感，有效融合两路检索的优点
- 避免某一路过强的主导——当语义检索返回弱相关结果时，关键词匹配可以"拯救"召回

### 参数配置

| 参数               | 默认值         | 说明                        |
| ---------------- | ----------- | ------------------------- |
| top\_k           | 5           | 最终返回的最大结果数                |
| score\_threshold | 0.7         | 稠密检索相似度下限（低于此值不参与融合）      |
| RRF k 常数         | 60          | Qdrant 默认值，控制排名对融合权重的影响强度 |
| prefetch limit   | top\_k \* 2 | 预取更多候选项，供 RRF 充分排序        |

**score\_threshold = 0.7 的选择理由**：

- 经过多次人工测试发现，0.7 是一个良好的平衡点
- 低于 0.7 的结果通常与问题语义差异较大，加入后反而会干扰 LLM
- 严格阈值意味着即使某路检索返回了低分结果，也不会通过 RRF 进入最终结果

### 知识库路由（kb\_name 过滤）

当 Agent 在调用 `retrieve_knowledge` 工具时指定了 `kb_name` 参数，Qdrant 查询会添加 Filter：

```python
filter_condition = qdrant_models.Filter(
    must=[
        qdrant_models.FieldCondition(
            key="kb_name",
            match=qdrant_models.MatchValue(value=kb_name),
        )
    ]
)
```

这使得 Agent 可以在多知识库场景下精确路由到最相关的知识库。

***

## 关键工程问题处理

### 1. 检索为空（No Retrieval）

**问题**：用户问题在知识库中没有相关内容，LLM 可能编造答案。

**解决方案**：

1. **Agent 级别**：System Prompt 明确要求"如果知识库中没有相关信息，说'抱歉，我暂时无法回答这个问题'"
2. **工具级别**：`retrieve_knowledge` 工具检索为空时返回空字符串，LLM 收到空结果后不再能编造
3. **测试验证**：通过 RAG Eval Pipeline 持续检测空检索场景的回答质量

### 2. 上下文超长（Context Overflow）

**问题**：多轮对话 + 长文档检索导致超出 LLM 上下文窗口。

**解决方案**：

1. **分块控制**：每个知识块限制在 400 字符（`CHUNK_SIZE=400`），加上 50 字符重叠
2. **top\_k 限制**：最多返回 5 条相关片段（`QDRANT_TOP_K=5`），控制注入 prompt 的信息量
3. **历史消息截断**：LangGraph Checkpointer 可配置历史窗口（当前使用默认行为）
4. **单次提问限制**：用户提问不超过 500 字，避免问题本身过长

### 3. LLM 幻觉（Hallucination）

**问题**：LLM 可能编造不存在的事实、混淆不同产品的功能。

**解决方案**：

1. **Prompt 约束**：回答要求 1-5 明确约束生成行为
2. **仅基于检索结果**：禁止 LLM 使用自身知识，必须依赖检索结果
3. **来源引用**：要求 LLM 在回答时引用具体的文档名称和章节（方便人工核验）
4. **相似度阈值**：score\_threshold = 0.7 确保只有高度相关的内容才会进入 prompt
5. **每日 Human-in-the-Loop**：通过反馈机制（like/dislike + 文字评价）收集用户对回答质量的判断

### 4. 调用频率控制

**问题**：恶意或误操作可能导致大量 API 调用消耗预算。

**解决方案**：

- 每用户每日调用上限（默认 100 次），跨天自动重置
- 内存计数 + 定期持久化，重启最多丢失 5 次计数
- 返回 HTTP 429 友好提示

### 5. API 异常处理

**问题**：Embedding API / LLM API 可能超时或限流。

**解决方案**：

- Embedding 调用：最多重试 2 次，每次间隔 1 秒
- LLM 调用：通过 `ChatOpenAI` 默认重试机制
- 后台任务异常：捕获到 `_errors` 字典，通过 SSE 的 `error` 事件通知前端

### 6. 多知识库下的大规模检索执行保障

针对企业级场景，当知识库文档非常多时（成百上千篇文档），系统设计了以下保障机制：

#### 6.1 分库路由减负

- 将文档按主题组织到不同的 `knowledge_bases` 中
- Agent 先根据 KB 描述和关键词判断该检索哪个知识库，缩小检索范围
- Qdrant 查询时通过 `kb_name` Filter 仅搜索目标 KB，大幅降低单次搜索的候选集

#### 6.2 RRF 融合的信息蒸馏

- 双路检索各取 `top_k * 2` 个候选项，经 RRF 融合后只保留 `top_k` 个
- 天然的信息蒸馏机制：从 N 个候选中选出最重要的 K 个
- score\_threshold = 0.7 进一步过滤低相关结果

#### 6.3 检索分段策略

`retrieve_knowledge` 工具的查询提示语描述了检索策略：

- 首次检索用原始问题 → 获取高相关结果
- 结果不充分时换种表述再检索 → 覆盖不同角度的信息
- Agent 可以多次调用工具，从不同角度覆盖知识需求

***

## 效果验证与评估

系统内置了 RAG 评估流水线（`app/scripts/rag_eval.py`），可自动化评估回答质量：

### 评估流程

1. **准备测试集**：`test_dataset.json` 包含测试问题、期望答案、期望检索上下文
2. **执行评估**：对每个测试问题，运行完整 Agent 链路
3. **提取结果**：从 Agent 执行记录中提取实际检索到的片段
4. **输出报告**：生成 `evals/eval-results.json` 和 `eval-report.md`

### 评估指标（人工判读）

| 指标    | 说明                 |
| ----- | ------------------ |
| 检索命中率 | 期望的上下文是否被正确召回      |
| 回答准确性 | LLM 的回答是否正确引用了检索内容 |
| 防幻觉表现 | 空检索时是否返回兜底话术       |
| 引用完整性 | 回答是否引用了正确的文档和章节    |

> 当前评估以人工核验为主，每次修改 Prompt 或检索参数后，运行 `rag_eval` 对比前后结果变化。

