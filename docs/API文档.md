# API 接口文档

> AI 智能客服系统 — 完整接口列表与使用说明

---

## 目录

- [概述](#概述)
- [通用说明](#通用说明)
- [认证模块](#1-认证模块-auth)
- [聊天模块](#2-聊天模块-chat)
- [会话模块](#3-会话模块-session)
- [知识库模块](#4-知识库模块-knowledge)
- [反馈模块](#5-反馈模块-feedback)
- [流式接口（SSE）说明](#6-流式接口-sse-说明)
- [错误处理](#7-错误处理)

---

## 概述

| 项目 | 说明 |
|------|------|
| 基础地址 | `http://<host>:7500` |
| 前端代理 | 开发模式下 `/api/*` → `http://127.0.0.1:7500`（自动剥离 `/api` 前缀） |
| 认证方式 | JWT Bearer Token |
| 数据格式 | JSON |
| 流式接口 | Server-Sent Events (SSE) |
| Swagger 文档 | `http://localhost:7500/docs` |

---

## 通用说明

### 认证方式

除登录/注册接口外，所有 API 需在请求头中携带 JWT Token：

```
Authorization: Bearer <access_token>
```

Token 有效期为 7 天（可通过 `.env` 配置）。

### 通用响应格式

**成功响应**：直接返回对应 JSON 对象或数组。

**错误响应**：

```json
{
  "detail": "错误描述信息"
}
```

### 状态码说明

| 状态码 | 含义 |
|--------|------|
| 200 | 请求成功 |
| 201 | 创建成功 |
| 202 | 已接受（异步处理） |
| 204 | 删除成功 / 无内容 |
| 400 | 请求参数错误 |
| 401 | 未认证（Token 缺失/无效/过期） |
| 404 | 资源不存在 |
| 409 | 资源冲突（如重复创建） |
| 429 | 频率超限（每日提问次数用尽） |
| 500 | 服务器内部错误 |

---

## 1. 认证模块 (`/auth`)

### 1.1 用户注册

```
POST /auth/register
```

**请求体**：

```json
{
  "email": "user@example.com",
  "password": "mypassword123"
}
```

**字段说明**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| email | string | 是 | 邮箱地址，需符合邮箱格式 |
| password | string | 是 | 密码（服务端 bcrypt 加密存储） |

**响应 (201)**：

```json
{
  "id": 1,
  "email": "user@example.com"
}
```

---

### 1.2 用户登录

```
POST /auth/login
```

**请求体**：

```json
{
  "email": "user@example.com",
  "password": "mypassword123"
}
```

**响应 (200)**：

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "email": "user@example.com"
  }
}
```

**字段说明**：

| 字段 | 类型 | 说明 |
|------|------|------|
| access_token | string | JWT Token，有效期 7 天 |
| token_type | string | 固定为 `bearer` |
| user | object | 用户基本信息 |

---

### 1.3 获取当前用户信息

```
GET /auth/me
```

**请求头**：`Authorization: Bearer <token>`

**响应 (200)**：

```json
{
  "id": 1,
  "email": "user@example.com"
}
```

---

## 2. 聊天模块 (`/chat`)

### 2.1 发起对话（问一个问题）

```
POST /chat/invoke
```

**请求头**：`Authorization: Bearer <token>`

**请求体**：

```json
{
  "query": "什么是 Auperator 智能运维系统？",
  "thread_id": null
}
```

**字段说明**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| query | string | 是 | 用户提问，不超过 500 字 |
| thread_id | string | 否 | 续接已有会话时传入，为空则创建新会话 |

**响应 (201)**：

```json
{
  "thread_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "session_id": 42
}
```

**字段说明**：

| 字段 | 类型 | 说明 |
|------|------|------|
| thread_id | string | 会话线程 ID，用于后续流式消费和停止 |
| session_id | int | 数据库中的会话记录 ID |

> **注意**：此接口仅创建后台 Agent 任务并返回 thread_id。实际的回复内容需要通过 SSE 流式接口消费。

---

### 2.2 流式获取回复

```
GET /chat/stream/{thread_id}
```

**请求头**：`Authorization: Bearer <token>`

**路径参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| thread_id | string | 发起对话时返回的 thread_id |

**响应 (200)**：SSE (text/event-stream)

> 详细的数据格式见第 6 节「流式接口（SSE）说明」。

---

### 2.3 停止对话

```
POST /chat/stop
```

**请求头**：`Authorization: Bearer <token>`

**请求体**：

```json
{
  "thread_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

**响应 (200)**：

```json
{
  "message": "对话已停止",
  "thread_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

---

## 3. 会话模块 (`/session`)

### 3.1 获取会话列表

```
GET /session/list
```

**请求头**：`Authorization: Bearer <token>`

**响应 (200)**：

```json
{
  "total": 2,
  "items": [
    {
      "thread_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "title": "什么是 Auperator 智能运维系统？",
      "created_at": "2026-06-13T10:00:00",
      "updated_at": "2026-06-13T10:05:00"
    },
    {
      "thread_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
      "title": "如何配置告警规则？",
      "created_at": "2026-06-12T14:00:00",
      "updated_at": "2026-06-12T14:03:00"
    }
  ]
}
```

---

### 3.2 获取会话详情（完整对话记录）

```
GET /session/{thread_id}
```

**请求头**：`Authorization: Bearer <token>`

**路径参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| thread_id | string | 会话的 thread_id |

**响应 (200)**：

```json
{
  "thread_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "什么是 Auperator 智能运维系统？",
  "messages": [
    {
      "id": "msg-001",
      "type": "human",
      "content": "什么是 Auperator 智能运维系统？",
      "result": null,
      "args": null,
      "user_rating": null
    },
    {
      "id": "msg-002",
      "type": "tool",
      "content": null,
      "result": "[1] 来源: auperator-intro.md > 产品概述\n    相关度: 0.92\n    内容: Auperator 是新一代智能运维...",
      "args": { "query": "Auperator 智能运维系统" },
      "user_rating": null
    },
    {
      "id": "msg-003",
      "type": "ai",
      "content": "Auperator 是一款智能运维系统，主要功能包括...",
      "result": null,
      "args": null,
      "user_rating": "like"
    }
  ]
}
```

**消息类型说明**：

| type | 说明 | 有效字段 |
|------|------|----------|
| human | 用户消息 | content |
| ai | AI 回复消息 | content, user_rating |
| tool | 工具调用结果（知识检索） | result, args |

---

### 3.3 删除会话

```
DELETE /session/{thread_id}
```

**请求头**：`Authorization: Bearer <token>`

**响应**：204 No Content

> 删除操作会：停止正在运行的任务、删除 LangGraph Checkpointer 中的 checkpoint 数据、删除 MySQL sessions 记录。

---

## 4. 知识库模块 (`/knowledge`)

### 4.1 获取知识库列表

```
GET /knowledge/bases
```

**请求头**：`Authorization: Bearer <token>`

**响应 (200)**：

```json
{
  "total": 1,
  "items": [
    {
      "name": "auperator",
      "doc_count": 3
    }
  ]
}
```

---

### 4.2 获取知识库详细信息

```
GET /knowledge/bases/detail
```

**请求头**：`Authorization: Bearer <token>`

**响应 (200)**：

```json
[
  {
    "id": 1,
    "name": "auperator",
    "description": "Auperator 智能运维系统产品文档",
    "keywords": "运维,监控,告警,自动化",
    "doc_count": 3,
    "created_at": "2026-06-10T10:00:00+08:00",
    "updated_at": "2026-06-13T15:00:00+08:00"
  }
]
```

---

### 4.3 获取单个知识库详情

```
GET /knowledge/bases/{kb_id}
```

**请求头**：`Authorization: Bearer <token>`

**响应 (200)**：同上 `KnowledgeBaseResponse` 格式。

---

### 4.4 创建知识库

```
POST /knowledge/bases
```

**请求头**：`Authorization: Bearer <token>`

**请求体**：

```json
{
  "name": "my-knowledge-base",
  "description": "我的知识库",
  "keywords": "关键词1,关键词2"
}
```

**字段说明**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | 是 | 知识库名称，唯一，对应磁盘目录 `knowledges/<name>/` |
| description | string | 否 | 知识库描述 |
| keywords | string | 否 | 逗号分隔的关键词，用于 Agent 路由判断 |

**响应 (201)**：

```json
{
  "id": 2,
  "name": "my-knowledge-base",
  "description": "我的知识库",
  "keywords": "关键词1,关键词2",
  "doc_count": 0,
  "created_at": "2026-06-13T16:00:00+08:00",
  "updated_at": "2026-06-13T16:00:00+08:00"
}
```

---

### 4.5 更新知识库

```
PUT /knowledge/bases/{kb_id}
```

**请求头**：`Authorization: Bearer <token>`

**请求体**：

```json
{
  "name": "renamed-kb",
  "description": "更新后的描述",
  "keywords": "新关键词"
}
```

所有字段均为可选，只传需要更新的字段。

**响应 (200)**：返回更新后的 `KnowledgeBaseResponse`。

---

### 4.6 删除知识库

```
DELETE /knowledge/bases/{kb_id}
```

**请求头**：`Authorization: Bearer <token>`

**响应 (200)**：

```json
{
  "message": "知识库已删除",
  "deleted_docs": 3
}
```

> 级联删除：删除知识库下的所有文档向量（Qdrant）、磁盘文件、MySQL 记录。

---

### 4.7 获取文档列表

```
GET /knowledge/list
```

**请求头**：`Authorization: Bearer <token>`

**查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| knowledge_base | string | 否 | 按知识库名称筛选 |
| kb_id | int | 否 | 按知识库 ID 筛选 |

**响应 (200)**：

```json
{
  "total": 3,
  "items": [
    {
      "id": 1,
      "kb_id": 1,
      "knowledge_base": "auperator",
      "file_path": "knowledges/auperator/auperator-intro.md",
      "original_filename": "auperator-intro.md",
      "file_size": 2048,
      "content_hash": "a1b2c3d4e5f6...",
      "status": "ready",
      "chunk_count": 12,
      "error_message": null,
      "created_at": "2026-06-10T10:00:00+08:00"
    }
  ]
}
```

**status 说明**：

| 状态 | 含义 |
|------|------|
| processing | 文档正在后台解析和向量化 |
| ready | 处理完成，可用于检索 |
| failed | 处理失败，查看 error_message 了解原因 |

---

### 4.8 获取单个文档详情

```
GET /knowledge/{doc_id}
```

**请求头**：`Authorization: Bearer <token>`

**响应 (200)**：返回单个 `KnowledgeDocResponse`。

---

### 4.9 上传文档

```
POST /knowledge/upload
```

**请求头**：`Authorization: Bearer <token>`（不要设 Content-Type，由 multipart 自动生成）

**请求体**（multipart/form-data）：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| file | file | 是 | 文档文件，支持 .md / .txt，最大 10MB |
| kb_id | int | 是 | 目标知识库 ID |

**响应 (202)**：

```json
{
  "id": 4,
  "kb_id": 1,
  "knowledge_base": "auperator",
  "file_path": "knowledges/auperator/new-doc.md",
  "original_filename": "new-doc.md",
  "file_size": 1536,
  "content_hash": "b2c3d4e5f6a7...",
  "status": "processing",
  "chunk_count": 0,
  "error_message": null,
  "created_at": "2026-06-13T17:00:00+08:00"
}
```

> 文档上传后立即返回（202 Accepted），后台异步进行解析 → 分块 → 嵌入 → 存储。前端需轮询文档列表以确认 status 变为 "ready"。

---

### 4.10 删除文档

```
DELETE /knowledge/{doc_id}
```

**请求头**：`Authorization: Bearer <token>`

**响应**：204 No Content

> 同时删除 Qdrant 中的向量、磁盘中的源文件、MySQL 中的记录。

---

## 5. 反馈模块 (`/feedback`)

### 5.1 提交/切换评价

```
POST /feedback
```

**请求头**：`Authorization: Bearer <token>`

**请求体**：

```json
{
  "message_id": "msg-003",
  "rating": "like",
  "comment": "回答很有帮助！"
}
```

**字段说明**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| message_id | string | 是 | 被评价消息的 UUID（来自 LangGraph Checkpointer） |
| rating | string | 是 | `like` 或 `dislike` |
| comment | string | 否 | 可选评价备注，最长 500 字 |

**行为说明**：

| 场景 | 行为 |
|------|------|
| 首次评价 | 创建新评价记录 |
| 相同 rating 再次提交 | 取消评价（删除记录），返回 204 |
| 不同 rating | 切换评价（如 like → dislike） |

**响应 (200)**：

```json
{
  "id": 1,
  "message_id": "msg-003",
  "rating": "like",
  "comment": "回答很有帮助！",
  "created_at": "2026-06-13T17:30:00"
}
```

**响应 (204)**：取消评价时返回无内容。

---

### 5.2 获取评价统计

```
GET /feedback/summary?message_id=msg-003
```

**查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| message_id | string | 是 | 消息 UUID |

**响应 (200)**：

```json
{
  "message_id": "msg-003",
  "like_count": 5,
  "dislike_count": 1
}
```

---

## 6. 流式接口（SSE）说明

### 6.1 概述

聊天回复通过 Server-Sent Events（SSE）实现流式输出。客户端通过 `GET /chat/stream/{thread_id}` 建立 SSE 连接后，服务端会持续推送事件直到回复完成。

### 6.2 SSE 事件格式

每条 SSE 消息以 `data:` 开头，后跟 JSON 数据，以 `\n\n` 结束。

### 6.3 事件类型

#### token — LLM 生成的文本片段

```json
{
  "type": "token",
  "content": "Auperator"
}
```

后续片段：

```json
{
  "type": "token",
  "content": " 是一款智能运维系统"
}
```

前端需将多个 token 片段拼接为完整回答。

#### tool_call — 工具调用开始

```json
{
  "type": "tool_call",
  "name": "retrieve_knowledge",
  "args": {
    "query": "什么是 Auperator"
  }
}
```

前端可展示"正在检索知识库..."等中间状态。

#### tool_result — 工具调用结果

```json
{
  "type": "tool_result",
  "name": "retrieve_knowledge",
  "result": "[1] 来源: auperator-intro.md > 产品概述\n    相关度: 0.92\n    内容: Auperator 是新一代智能运维..."
}
```

#### sources — 知识来源列表（当前为保留字段，后端预留接口）

```json
{
  "type": "sources",
  "sources": [
    "auperator-intro.md - 产品概述",
    "faq.md - 常见问题"
  ]
}
```

#### error — 错误信息

```json
{
  "type": "error",
  "message": "检索服务暂时不可用，请稍后重试"
}
```

#### done — 回复完成

```json
{
  "type": "done"
}
```

### 6.4 典型流程示例

```
---> POST /chat/invoke  {"query": "Auperator 有哪些功能？"}
<--- 201 {"thread_id": "xxx", "session_id": 42}

---> GET /chat/stream/xxx  (SSE)
<--- data: {"type": "tool_call", "name": "retrieve_knowledge", "args": {"query": "Auperator 功能"}}
<--- data: {"type": "tool_result", "name": "retrieve_knowledge", "result": "[1] 来源: ..."}
<--- data: {"type": "token", "content": "Auperator"}
<--- data: {"type": "token", "content": " 提供以下核心功能："}
<--- data: {"type": "token", "content": "1. 智能监控..."}
<--- data: {"type": "sources", "sources": ["auperator-intro.md"]}
<--- data: {"type": "done"}
```

### 6.5 前端处理建议

```javascript
// 伪代码示例：SSE 消费逻辑
const reader = response.body.getReader();
const decoder = new TextDecoder();
let buffer = '';

while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  buffer += decoder.decode(value, { stream: true });
  const lines = buffer.split('\n');
  buffer = lines.pop() || '';
  for (const line of lines) {
    if (line.startsWith('data: ')) {
      const data = JSON.parse(line.slice(6));
      switch (data.type) {
        case 'token': appendToOutput(data.content); break;
        case 'sources': showSources(data.sources); break;
        case 'tool_call': showToolCallState(data.name, data.args); break;
        case 'tool_result': showToolResult(data.result); break;
        case 'error': showError(data.message); break;
        case 'done': finishStreaming(); break;
      }
    }
  }
}
```

---

## 7. 错误处理

### 7.1 常见错误码

| HTTP 状态码 | 场景 | 示例响应 |
|-------------|------|----------|
| 400 | 参数校验失败 | `{"detail": "提问长度不能超过500字"}` |
| 400 | 不支持的文件格式 | `{"detail": "不支持的文件格式: .pdf，仅支持 .md, .txt"}` |
| 401 | Token 缺失/无效 | `{"detail": "未提供认证令牌"}` |
| 404 | 资源不存在 | `{"detail": "会话不存在"}` |
| 409 | 重复创建 | `{"detail": "知识库「my-kb」已存在"}` |
| 429 | 调用频率超限 | `{"detail": "今日对话次数已用尽（100 次），请明天再试"}` |
| 500 | 服务器内部错误 | `{"detail": "内部错误"}` |

### 7.2 流式接口的错误

SSE 流中的错误通过 `error` 事件推送，HTTP 状态码仍为 200。客户端应同时监听：
- HTTP 级别的错误（连接建立失败、401 等）
- SSE 事件中的 `error` 类型消息
