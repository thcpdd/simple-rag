# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# ─── Backend (uv) ───
cd backend && uv run uvicorn main:app --reload --host 0.0.0.0 --port 7500
cd backend && uv run python main.py          # alternative
cd backend && uv sync                        # install/sync deps
cd backend && uv run ruff check app/         # lint
cd backend && uv run python -m app.scripts.init_kb        # init KB (parse→embed→store)
cd backend && uv run python -m app.scripts.test_retrieval  # test vector search

# ─── Frontend (pnpm) ───
cd frontend && pnpm dev       # Vite dev server (port 5173, proxies /api → :7500)
cd frontend && pnpm build     # tsc + vite build → dist/
cd frontend && pnpm lint      # ESLint
```

## Security Warning

The `.env` file contains live API keys and database credentials — it is gitignored. Never commit it or paste its contents. Use `.env.example` as a reference template.

## Project Structure

```
simple-rag/
├── backend/                  # FastAPI + LangGraph backend (Python, uv)
│   ├── app/
│   │   ├── agents/               # LangGraph agent definitions
│   │   │   ├── builder.py            # build_agent(): LLM + retrieval_tool + checkpointer
│   │   │   └── retrieval_tool.py     # @tool wrapping embed() + vector_store.search()
│   │   ├── api/                 # FastAPI route handlers
│   │   │   ├── auth.py              # POST /auth/register, /auth/login, GET /auth/me
│   │   │   ├── chat.py              # POST /chat/invoke, GET /chat/stream/{id}, POST /chat/stop
│   │   │   ├── knowledge.py         # GET/POST/DELETE /knowledge/*
│   │   │   ├── session.py           # GET /session/list, GET /session/{thread_id}
│   │   │   └── deps.py              # get_current_user() — HTTP Bearer JWT dependency
│   │   ├── core/                # Infrastructure layer
│   │   │   ├── config.py            # pydantic-settings (.env based)
│   │   │   ├── database.py          # SQLAlchemy async engine + session (MySQL)
│   │   │   └── security.py          # bcrypt hash, JWT create/decode
│   │   ├── models/              # SQLAlchemy ORM models
│   │   │   ├── user.py              # users table
│   │   │   ├── knowledge_doc.py     # knowledge_docs table (file_path, md5 hash, status)
│   │   │   └── session.py           # sessions table (links user_id ↔ thread_id)
│   │   ├── schemas/             # Pydantic request/response models per API module
│   │   │   ├── user.py
│   │   │   ├── knowledge.py
│   │   │   ├── chat.py
│   │   │   └── session.py
│   │   ├── scripts/             # CLI utilities (run via -m)
│   │   │   ├── init_kb.py           # Batch init: scan → dedup → parse → embed → store
│   │   │   └── test_retrieval.py    # Interactive CLI for testing vector search
│   │   ├── services/            # Business logic layer
│   │   │   ├── user.py              # register / login / get_user_by_id
│   │   │   ├── knowledge.py         # process_document() / delete_document() pipeline
│   │   │   ├── document_parser.py   # parse_document() dispatcher (.md vs .txt)
│   │   │   ├── text_splitter.py     # MarkdownHeaderTextSplitter + RecursiveCharacterTextSplitter
│   │   │   ├── embedding.py         # OpenAI-compatible embedding (single + batch, retry)
│   │   │   ├── vector_store.py      # Qdrant CRUD (ensure_collection, upsert, search, delete)
│   │   │   └── chat_task_manager.py # Agent task lifecycle: invoke/stream/stop asyncio management
│   │   └── utils/
│   │       └── logging.py           # Colored console + file logging, unified uvicorn config
│   ├── main.py                 # FastAPI entry: lifespan (auto-create tables), CORS, router registration
│   ├── pyproject.toml          # Python deps managed by uv
│   └── .env.example            # Required env vars (copy to .env)
├── frontend/                  # Vite + React + TypeScript SPA (pnpm)
│   ├── src/
│   │   ├── components/
│   │   │   ├── auth/              # ProtectedRoute (JWT guard in localStorage)
│   │   │   ├── chat/              # Chat page components
│   │   │   ├── knowledge/         # Knowledge base management components
│   │   │   └── ui/                # shadcn/ui primitives (button, dialog, card, etc.)
│   │   ├── layouts/
│   │   │   └── AppLayout.tsx      # Sidebar + Outlet, nav links, user dropdown
│   │   ├── pages/
│   │   │   ├── ChatPage.tsx       # Chat with SSE streaming
│   │   │   ├── KnowledgePage.tsx  # Document upload & management
│   │   │   ├── LoginPage.tsx
│   │   │   └── RegisterPage.tsx
│   │   ├── lib/
│   │   │   ├── api.ts             # API client (fetch wrapper + SSE stream helper + types)
│   │   │   └── utils.ts           # Tailwind class merge utility
│   │   ├── App.tsx                # Route definitions (react-router-dom)
│   │   ├── main.tsx               # Entry point
│   │   └── index.css              # Tailwind v4 import
│   ├── vite.config.ts          # Tailwind + React plugins, /api proxy → :7500, @ alias
│   ├── package.json
│   └── pnpm-lock.yaml
└── knowledges/                 # Knowledge base source documents
    └── auperator/              # Product docs for Auperator intelligent ops system
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

### Frontend Architecture (React SPA)

```
[Browser] ← react-router-dom → [Pages] → [api.ts fetch/SSE] → Vite proxy → FastAPI
                                       ↓
                              localStorage (JWT token, user info)
```

- **Routing**: `react-router-dom v7` — public routes (`/login`, `/register`) and protected routes (`/chat`, `/knowledge`) wrapped in `<ProtectedRoute>` which checks `localStorage.getItem('access_token')`.
- **Auth flow**: Login/Register → backend returns JWT → stored in localStorage → attached as `Authorization: Bearer <token>` header on every request via `api.ts`.
- **API client** (`lib/api.ts`): Generic `request<T>()` wrapper around `fetch()` with automatic JWT injection and JSON parsing. Separate `createSSEStream()` for SSE-based chat streaming (token/sources/error/done events).
- **Chat streaming**: `POST /chat/invoke` returns `{thread_id}` → `GET /chat/stream/{thread_id}` via SSE → renders tokens incrementally via `useState` + `useEffect` with `AbortController` for stop support.
- **UI components**: shadcn/ui primitives (Radix-based) + Tailwind CSS v4 + lucide-react icons. `@` path alias maps to `src/`.
- **Dev proxy**: Vite dev server proxies `/api/*` → `http://127.0.0.1:7500` (strips `/api` prefix). No CORS issues in development.

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

### Full-Stack Development Workflow

1. Start backend: `cd backend && uv run uvicorn main:app --reload --host 0.0.0.0 --port 7500`
2. Start frontend (separate terminal): `cd frontend && pnpm dev` (port 5173)
3. Frontend proxies `/api/*` to backend, so open `http://localhost:5173` in browser.
4. To initialize knowledge base: `cd backend && uv run python -m app.scripts.init_kb`

### Dependencies

- **MySQL** + **Qdrant** as external services (configured via .env)
- **OpenAI-compatible** API for chat model
- **SiliconFlow** (or any OpenAI-compatible) API for embeddings (e.g., `Qwen/Qwen3-Embedding-8B`, 4096-dim)
- **LangChain** for text splitters, tool definition, and agent creation
- **LangGraph** for agent orchestration with checkpointing
- **FastAPI** + **uvicorn** for the web server
- **SQLAlchemy** (async) + **aiomysql** for the ORM
