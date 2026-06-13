# AI 智能客服系统 — 后端服务

> 基于 FastAPI + LangGraph + RAG 的智能客服后端，提供知识库管理、Agent 对话（SSE 流式）、用户认证、反馈评价等完整能力。

---

## 目录

- [快速开始](#快速开始)
- [配置说明](#配置说明)
- [项目结构](#项目结构)
- [API 文档](#api-文档)
- [核心架构](#核心架构)
- [开发指南](#开发指南)
- [部署](#部署)

---

## 快速开始

### 前置依赖

- Python >= 3.11
- [uv](https://docs.astral.sh/uv/) 包管理器
- MySQL 数据库（示例端口 7334）
- Qdrant 向量数据库（示例端口 7333）
- OpenAI 兼容的大模型 API
- 嵌入模型 API（如 SiliconFlow）

### 安装

```bash
cd backend

# 同步依赖
uv sync

# 复制环境变量
cp .env.example .env
# 编辑 .env 填入实际的 API Key 和连接信息
```

### 启动

```bash
# 开发模式（热重载）
uv run uvicorn main:app --reload --host 0.0.0.0 --port 7500

# 或者直接运行
uv run python main.py
```

服务启动后访问 `http://localhost:7500/docs` 查看 Swagger 文档。

### 初始化知识库

```bash
# 扫描 knowledges/<kb_name>/ 目录下的文件，解析 → 分块 → 嵌入 → 存入 Qdrant
uv run python -m app.scripts.init_kb
```

### 其他脚本

```bash
# 检索测试（交互式 CLI）
uv run python -m app.scripts.test_retrieval

# RAG 评估流水线
uv run python -m app.scripts.rag_eval
```

---

## 配置说明

通过 `.env` 文件配置（参考 `.env.example`），由 `app/core/config.py` 中的 `pydantic-settings` 加载。

| 变量 | 说明 | 示例值 |
|------|------|--------|
| `DB_HOST` / `DB_PORT` / `DB_USER` / `DB_PASSWORD` / `DB_NAME` | MySQL 连接配置 | 127.0.0.1:7334 |
| `QDRANT_HOST` / `QDRANT_PORT` / `QDRANT_API_KEY` / `QDRANT_COLLECTION_NAME` | Qdrant 向量库配置 | 127.0.0.1:7333 |
| `OPENAI_BASE_URL` / `OPENAI_MODEL` / `OPENAI_API_KEY` | 对话模型 API | deepseek/deepseek-v4-flash |
| `EMBEDDING_API_BASE_URL` / `EMBEDDING_API_KEY` / `EMBEDDING_MODEL` / `EMBEDDING_VECTOR_SIZE` | 嵌入模型 API | Qwen/Qwen3-Embedding-8B, 4096 维 |

---

## 项目结构

```
backend/
├── app/
│   ├── agents/                # LangGraph Agent 定义
│   │   ├── builder.py             # build_agent(): 构建 LLM + tool + checkpointer
│   │   └── retrieval_tool.py      # @tool: 嵌入 + 向量搜索（含 kb_name 过滤）
│   ├── api/                   # FastAPI 路由层
│   │   ├── auth.py                # POST /auth/register, /auth/login, GET /auth/me
│   │   ├── chat.py                # POST /chat/invoke, GET /chat/stream/{id}, POST /chat/stop
│   │   ├── feedback.py            # POST /feedback, GET /feedback/summary
│   │   ├── knowledge.py           # 知识库 CRUD (bases/) + 文档 CRUD (upload/delete/list)
│   │   ├── session.py             # GET /session/list, GET /session/{thread_id}
│   │   └── deps.py                # get_current_user() — JWT Bearer 认证依赖
│   ├── core/                  # 基础设施层
│   │   ├── config.py              # pydantic-settings (.env 加载)
│   │   ├── database.py            # SQLAlchemy async engine + session
│   │   └── security.py            # bcrypt 哈希 + JWT 签发/验证
│   ├── models/                # SQLAlchemy ORM 模型
│   │   ├── user.py                # users 表
│   │   ├── knowledge_base.py      # knowledge_bases 表
│   │   ├── knowledge_doc.py       # knowledge_docs 表
│   │   ├── session.py             # sessions 表
│   │   └── feedback.py            # feedbacks 表
│   ├── schemas/               # Pydantic 请求/响应模型
│   │   ├── user.py
│   │   ├── knowledge.py
│   │   ├── chat.py
│   │   ├── session.py
│   │   └── feedback.py
│   ├── scripts/               # CLI 工具（通过 -m 运行）
│   │   ├── init_kb.py             # 批量初始化：扫描 → 去重 → 解析 → 嵌入 → 存储
│   │   ├── test_retrieval.py      # 交互式检索测试 CLI
│   │   └── rag_eval.py            # RAG 评估流水线
│   ├── services/              # 业务逻辑层
│   │   ├── user.py                # 注册 / 登录 / 用户查询
│   │   ├── knowledge.py           # 知识库 CRUD + 文档 CRUD + 后台处理
│   │   ├── document_parser.py     # parse_document() 调度器 (.md / .txt)
│   │   ├── text_splitter.py       # MarkdownHeaderTextSplitter + RecursiveCharacterTextSplitter
│   │   ├── embedding.py           # OpenAI 兼容的嵌入（单条 + 批量 + 重试）
│   │   ├── vector_store.py        # Qdrant CRUD + 混合检索（稠密 + 稀疏 + RRF 融合）
│   │   ├── chat_task_manager.py   # Agent 任务生命周期管理（asyncio Task/Queue）
│   │   ├── daily_usage.py         # 每用户每日调用频率限制
│   │   └── feedback.py            # 反馈 upsert（切换 like/dislike）+ 统计
│   └── utils/
│       └── logging.py             # 彩色控制台 + 文件日志，统一 uvicorn 配置
├── main.py                   # FastAPI 入口：生命周期、CORS、路由注册
├── pyproject.toml            # Python 依赖（uv 管理）
├── .env.example              # 环境变量模板
└── README.md                 # 本文件
```

---

## API 文档

启动服务后访问 `http://localhost:7500/docs` 可交互式测试所有接口。

### 认证 (`/auth`)

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| POST | `/auth/register` | 注册新用户 | 无需 |
| POST | `/auth/login` | 登录，返回 JWT Token | 无需 |
| GET | `/auth/me` | 获取当前用户信息 | Bearer |

### 聊天 (`/chat`)

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/chat/invoke` | 发起对话，返回 `thread_id` |
| GET | `/chat/stream/{thread_id}` | SSE 流式获取回复（token / tool_call / sources / done） |
| POST | `/chat/stop` | 停止正在进行的 Agent 任务 |

### 会话 (`/session`)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/session/list` | 获取当前用户的会话列表 |
| GET | `/session/{thread_id}` | 获取完整对话历史 |

### 知识库 (`/knowledge`)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/knowledge/bases` | 获取知识库列表 |
| POST | `/knowledge/bases` | 创建知识库 |
| PUT | `/knowledge/bases/{id}` | 更新知识库 |
| DELETE | `/knowledge/bases/{id}` | 删除知识库 |
| POST | `/knowledge/upload` | 上传文档（指定 kb_id） |
| GET | `/knowledge/docs` | 获取某知识库的文档列表 |
| DELETE | `/knowledge/docs/{id}` | 删除文档 |

### 反馈 (`/feedback`)

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/feedback` | 提交/切换 like/dislike 评价 |
| GET | `/feedback/summary` | 获取评价统计 |

---

## 核心架构

### 分层设计

```
API 路由 (api/)  →  服务层 (services/)  →  ORM 模型 (models/)  +  基础设施 (core/)
```

- **路由层**: 处理 HTTP 请求/响应，参数校验
- **服务层**: 业务逻辑核心，不依赖 HTTP 上下文
- **模型层**: SQLAlchemy ORM 定义
- **基础设施**: 配置、数据库引擎、安全工具

### Agent 对话流程

```
用户输入
    ↓
POST /chat/invoke
    → chat_task_manager.invoke(query)
        → 创建 asyncio.Task + asyncio.Queue
        → Task 运行 Agent（LLM + retrieve_knowledge 工具）
        → Agent 推送 (event_type, data) → Queue
    ← 返回 thread_id
    ↓
GET /chat/stream/{thread_id} (SSE)
    → 消费 Queue 事件
    → 流式输出: token / tool_call / tool_result / sources / done
    ↓
前端增量渲染
```

### 知识库 RAG 流水线

```
文档上传
    → 创建 knowledge_doc 记录 (status=processing)
    → 保存文件到 knowledges/<kb_name>/
    → 后台任务:
        parse_document() → text_splitter 分块
        → embed_batch() 嵌入
        → Qdrant upsert
    → 更新状态为 ready (或 failed)
```

### 混合检索（稠密 + 稀疏 + RRF 融合）

`vector_store.py` 使用 Qdrant `query_points` API 实现混合检索：

1. **稠密路径**: 语义向量搜索（cosine 距离，4096 维）
2. **稀疏路径**: BM25 风格关键词搜索（Qdrant 内置 IDF 修饰器）
3. **RRF 融合**: 两路 Prefetch + FusionQuery(fusion=Fusion.RRF) 合并结果
4. **后过滤**: 按 score_threshold（默认 0.7）+ kb_name 过滤

### 多知识库路由

- 每个知识库有唯一 `name`，对应 `knowledges/<name>/` 目录
- Qdrant payload 中存储 `kb_name`，支持字段过滤
- Agent 系统提示自动注入所有 KB 的 name/description/keywords
- `retrieve_knowledge` 工具接受可选 `kb_name` 参数

### 会话持久化

- `sessions` 表存储 user_id ↔ thread_id 映射
- 完整对话历史通过 **LangGraph AIOMySQLSaver** 持久化
- Agent 任务状态在内存中管理，完成后 60s 自动清理

---

## 开发指南

### 代码规范

```bash
# 代码检查
uv run ruff check app/

# 格式化检查
uv run ruff format --check app/

# 自动修正
uv run ruff check --fix app/
```

### 添加新 API

1. 在 `app/schemas/` 中定义 Pydantic 请求/响应模型
2. 在 `app/services/` 中实现业务逻辑
3. 在 `app/api/` 中创建路由器
4. 在 `app/main.py` 中注册路由器 `app.include_router()`

### 添加新模型

1. 在 `app/models/` 中定义 SQLAlchemy 模型（继承 `Base`）
2. 确保在 `app/main.py` 的 `lifespan` 中被 `import app.models` 引入
3. 在 `app/services/` 中实现对应的 CRUD 操作

### 常用调试

```bash
# 直接运行（不走 uvicorn 热重载，适合调试）
uv run python main.py

# 检查路由注册情况
uv run python -c "import main; [print(r.path, r.methods) for r in main.app.routes]"
```

---

## 部署

### 生产模式启动

```bash
uv run uvicorn main:app --host 0.0.0.0 --port 7500 --workers 4
```

### 环境变量

确保 `.env` 文件配置正确，尤其注意：

- `EMBEDDING_VECTOR_SIZE` 必须与嵌入模型的实际输出维度一致
- 各 API Key 需具有相应服务权限
- MySQL 和 Qdrant 需提前创建好数据库/Collection

### 外部依赖

| 服务 | 用途 | 版本要求 |
|------|------|----------|
| MySQL | 元数据存储（用户、会话、文档记录） | 8.0+ |
| Qdrant | 向量存储与混合检索 | 1.10+ |
| OpenAI 兼容 API | 大模型对话 | 任意 |
| 嵌入模型 API | 文本嵌入 | 输出维度与配置一致 |
