# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run the FastAPI dev server (from backend/)
cd backend && uv run uvicorn main:app --reload --host 0.0.0.0 --port 7500

# Or use main.py directly:
cd backend && uv run python main.py

# Initialize knowledge base (parse all docs in knowledges/ → embed → Qdrant + MySQL)
cd backend && uv run python -m app.scripts.init_kb

# Interactive retrieval test (requires init_kb first)
cd backend && uv run python -m app.scripts.test_retrieval

# Install / sync dependencies
cd backend && uv sync

# Activate venv
source backend/.venv/bin/activate

# Lint with ruff (if installed)
cd backend && uv run ruff check app/
```

## Security Warning

The `.env` file contains live API keys and database credentials — it is gitignored. Never commit it or paste its contents. Use `.env.example` as a reference template.

## Project Structure

```
simple-rag/
├── backend/
│   ├── app/
│   │   ├── agents/            # LangGraph agent definitions
│   │   │   ├── builder.py         # build_agent(): LLM + retrieval_tool + checkpointer
│   │   │   └── retrieval_tool.py  # @tool wrapping embed() + vector_store.search()
│   │   ├── api/               # FastAPI route handlers
│   │   │   ├── auth.py            # POST /auth/register, /auth/login, GET /auth/me
│   │   │   ├── chat.py            # POST /chat/invoke, GET /chat/stream/{id}, POST /chat/stop
│   │   │   ├── knowledge.py       # GET/POST/DELETE /knowledge/*
│   │   │   ├── session.py         # GET /session/list, GET /session/{thread_id}
│   │   │   └── deps.py            # get_current_user() — HTTP Bearer JWT dependency
│   │   ├── core/              # Infrastructure layer
│   │   │   ├── config.py          # pydantic-settings (.env based)
│   │   │   ├── database.py        # SQLAlchemy async engine + session (MySQL)
│   │   │   └── security.py        # bcrypt hash, JWT create/decode
│   │   ├── models/            # SQLAlchemy ORM models
│   │   │   ├── user.py            # users table
│   │   │   ├── knowledge_doc.py   # knowledge_docs table (file_path, md5 hash, status)
│   │   │   └── session.py         # sessions table (links user_id ↔ thread_id)
│   │   ├── schemas/           # Pydantic request/response models per API module
│   │   │   ├── user.py
│   │   │   ├── knowledge.py
│   │   │   ├── chat.py
│   │   │   └── session.py
│   │   ├── scripts/           # CLI utilities (run via -m)
│   │   │   ├── init_kb.py         # Batch init: scan → dedup → parse → embed → store
│   │   │   └── test_retrieval.py  # Interactive CLI for testing vector search
│   │   ├── services/          # Business logic layer
│   │   │   ├── user.py            # register / login / get_user_by_id
│   │   │   ├── knowledge.py       # process_document() / delete_document() pipeline
│   │   │   ├── document_parser.py # parse_document() dispatcher (.md vs .txt)
│   │   │   ├── text_splitter.py   # MarkdownHeaderTextSplitter + RecursiveCharacterTextSplitter
│   │   │   ├── embedding.py       # OpenAI-compatible embedding (single + batch, retry)
│   │   │   ├── vector_store.py    # Qdrant CRUD (ensure_collection, upsert, search, delete)
│   │   │   └── chat_task_manager.py #  Agent task lifecycle: invoke/stream/stop asyncio management
│   │   └── utils/
│   │       └── logging.py         # Colored console + file logging, unified uvicorn config
│   ├── main.py                # FastAPI entry: lifespan (auto-create tables), CORS, router registration
│   ├── pyproject.toml         # Python deps managed by uv
│   └── .env.example           # Required env vars (copy to .env)
└── knowledges/                # Knowledge base documents (the "source of truth")
    └── auperator/             # Product docs for the Auperator intelligent ops system
```

## Architecture

### Layered Pattern (FastAPI)

API routes (`api/`) call services (`services/`), which use models (`models/`) and core infra (`core/`). Services are the business logic layer — keep them free of HTTP concerns.

### Knowledge RAG Pipeline

```
file upload → parse_document() → split into chunks → embed_batch() → upsert to Qdrant
     ↓
MySQL record (KnowledgeDoc) created with status tracking
```

### Chat / Agent Streaming Architecture

```
POST /chat/invoke
  → chat_task_manager.invoke(query)
    → creates asyncio.Task + asyncio.Queue
    → Task runs Agent (LLM + retrieve_knowledge tool)
    → Agent pushes (event_type, data) tuples into Queue
    → returns thread_id

GET /chat/stream/{thread_id}  (SSE)
  → chat_task_manager.stream(thread_id)
    → consumes Queue events
    → yields SSE data: token / sources / error / done

POST /chat/stop
  → chat_task_manager.stop(thread_id)
    → cancels asyncio.Task
```

### Session Persistence

- `sessions` table in MySQL stores user ↔ thread_id mapping and a display title.
- Full conversation history is persisted via **LangGraph AIOMySQLSaver** checkpointer.
- `GET /session/list` returns session metadata from MySQL.
- `GET /session/{thread_id}` recovers full message history from the checkpointer.

### Agent Building

`agents/builder.py` uses `langchain.agents.create_agent()` to construct a LangGraph agent with:
- LLM (ChatOpenAI, configured via .env)
- `retrieve_knowledge` tool (LangChain @tool wrapping embed + vector search)
- Optional AIOMySQLSaver checkpointer for conversation state
- System prompt enforcing knowledge-only answers with source citations

### Key Design Decisions

- **Agentic RAG**: `retrieval_tool.py` wraps vector search as a LangChain `@tool`. The LLM decides when to retrieve, avoiding unnecessary embedding calls for non-knowledge queries.
- **Dual storage**: MySQL stores document metadata (status, md5 hash, chunk count); Qdrant stores vectors and chunk content. Deletion removes from both.
- **Idempotent init**: `init_kb.py` computes MD5 per file, skips existing hashes in MySQL.
- **Async throughout**: SQLAlchemy async session, AsyncOpenAI, AsyncQdrantClient, asyncio task/queue for streaming.
- **Config via .env**: All infra endpoints, keys, and model names in `config.py` via `pydantic-settings`.
- **Singleton clients**: Embedding, Qdrant, ChatOpenAI, and checkpointer are lazily initialized singletons.
- **Markdown chunking**: Two-pass — first by `##`/`###` headers (preserving section metadata), then recursive split for long sections (chunk_size=400, overlap=50).
- **Embedding batch via gather**: `embed_batch()` uses `asyncio.gather` with per-item retry.
- **No tests**: The project currently has no test suite.

### Dependencies

- **MySQL** + **Qdrant** as external services (configured via .env)
- **OpenAI-compatible** API for chat model
- **SiliconFlow** (or any OpenAI-compatible) API for embeddings (e.g., `Qwen/Qwen3-Embedding-8B`, 4096-dim)
- **LangChain** for text splitters, tool definition, and agent creation
- **LangGraph** for agent orchestration with checkpointing
- **FastAPI** + **uvicorn** for the web server
- **SQLAlchemy** (async) + **aiomysql** for the ORM
