# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# ─── Backend (uv) ───
cd backend && uv run uvicorn main:app --reload --host 0.0.0.0 --port 7500
cd backend && uv run python main.py          # alternative
cd backend && uv sync                        # install/sync deps
cd backend && uv run ruff check app/         # lint
cd backend && uv run ruff format --check app/  # check formatting
cd backend && uv run python -m app.scripts.init_kb        # init KB (parse→embed→store)
cd backend && uv run python -m app.scripts.test_retrieval  # test vector search
cd backend && uv run python -m app.scripts.rag_eval     # run RAG evaluation pipeline (reads test_dataset.json, outputs to evals/)

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
│   │   │   ├── feedback.py          # POST /feedback, GET /feedback/summary
│   │   │   ├── knowledge.py         # Full KB CRUD (bases/) + doc CRUD (list/upload/delete)
│   │   │   ├── session.py           # GET /session/list, GET /session/{thread_id}
│   │   │   └── deps.py              # get_current_user() — HTTP Bearer JWT dependency
│   │   ├── core/                # Infrastructure layer
│   │   │   ├── config.py            # pydantic-settings (.env based)
│   │   │   ├── database.py          # SQLAlchemy async engine + session (MySQL)
│   │   │   └── security.py          # bcrypt hash, JWT create/decode
│   │   ├── models/              # SQLAlchemy ORM models
│   │   │   ├── user.py              # users table
│   │   │   ├── knowledge_doc.py     # knowledge_docs table (file_path, md5 hash, status, kb_id)
│   │   │   ├── knowledge_base.py    # knowledge_bases table (name, description, keywords)
│   │   │   ├── session.py           # sessions table (links user_id ↔ thread_id)
│   │   │   └── feedback.py          # feedbacks table (user_id, message_id, rating: like/dislike)
│   │   ├── schemas/             # Pydantic request/response models per API module
│   │   │   ├── user.py
│   │   │   ├── knowledge.py
│   │   │   ├── chat.py
│   │   │   ├── session.py
│   │   │   └── feedback.py
│   │   ├── scripts/             # CLI utilities (run via -m)
│   │   │   ├── init_kb.py           # Batch init: scan → dedup → parse → embed → store
│   │   │   ├── test_retrieval.py    # Interactive CLI for testing vector search
│   │   │   └── rag_eval.py          # RAG eval pipeline: runs Agent on test_dataset.json, outputs structured results
│   │   ├── services/            # Business logic layer
│   │   │   ├── user.py              # register / login / get_user_by_id
│   │   │   ├── knowledge.py         # KB CRUD (create/update/delete knowledge_bases) + doc CRUD + background processing
│   │   │   ├── document_parser.py   # parse_document() dispatcher (.md vs .txt)
│   │   │   ├── text_splitter.py     # MarkdownHeaderTextSplitter + RecursiveCharacterTextSplitter
│   │   │   ├── embedding.py         # OpenAI-compatible embedding (single + batch, retry)
│   │   │   ├── vector_store.py      # Qdrant CRUD with mixed retrieval (dense + sparse, RRF fusion)
│   │   │   ├── chat_task_manager.py # Agent task lifecycle: invoke/stream/stop asyncio management
│   │   │   ├── daily_usage.py       # Per-user daily call rate limiter (100 calls/day, disk-persisted)
│   │   │   └── feedback.py          # Feedback upsert (toggle like/dislike) + summary stats
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
├── knowledges/                 # Knowledge base source documents (one subdirectory per KB)
│   └── auperator/              # Product docs for Auperator intelligent ops system
└── evals/                      # RAG evaluation reports & results (generated by rag_eval.py)
    ├── eval-report-v1.md
    ├── eval-report-v2.md
    ├── eval-results-v1.json
    └── eval-results-v2.json
```

## Architecture

### Layered Pattern (FastAPI)

API routes (`api/`) call services (`services/`), which use models (`models/`) and core infra (`core/`). Services are the business logic layer — keep them free of HTTP concerns.

### Knowledge RAG Pipeline

```
file upload → create knowledge_doc record (status=processing)
           → save file to knowledges/<kb_name>/ dir
           → background task (FastAPI BackgroundTasks):
               parse_document() → split into chunks → embed_batch() → upsert to Qdrant
               → update status to "ready" (or "failed" on error)
     ↓
MySQL record (KnowledgeDoc) tracks status, chunk_count, error_message
Qdrant payload stores source, kb_name, section, subsection, content
```

- **Multi-KB support**: Each document belongs to a `knowledge_base` (MySQL `knowledge_bases` table). Disk directories under `knowledges/` map 1:1 to KB names. Qdrant payload includes `kb_name` for filtered search.
- **Background processing**: Uploads return immediately (HTTP 202). Document parsing/embedding runs via `BackgroundTasks`, with polling (2s interval) on the frontend to track `processing` → `ready` status changes.
- **Dual cleanup**: Deleting a document or knowledge base removes vectors from Qdrant, deletes the source file from disk, and removes the MySQL record.

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
    → yields SSE data: token / tool_call / tool_result / sources / error / done

POST /chat/stop
  → chat_task_manager.stop(thread_id)
    → cancels asyncio.Task
```

### Session Persistence

- `sessions` table in MySQL stores user ↔ thread_id mapping and a display title.
- Full conversation history is persisted via **LangGraph AIOMySQLSaver** checkpointer (`langgraph-checkpoint-mysql[aiomysql]`).
- `GET /session/list` returns session metadata from MySQL.
- `GET /session/{thread_id}` recovers full message history from the checkpointer.
- **In-memory task state**: `chat_task_manager.py` maintains three global dicts (`_tasks`, `_queues`, `_errors`) keyed by thread_id for active conversation management. Tasks are cleaned up 60s after completion via `call_later`.

### Multi-Knowledge-Base System

```
GET/POST/PUT/DELETE /knowledge/bases[/{id}]  → CRUD for knowledge_bases (MySQL)
GET/POST/DELETE      /knowledge/docs          → document management per KB
POST                 /knowledge/upload        → upload doc to a specific KB
```

- `knowledge_bases` table stores `name` (unique, maps to `knowledges/<name>/` subdirectory), `description`, `keywords`.
- Agent system prompt is dynamically generated from all KBs at build time, listing each KB's name, description, and keywords so the LLM can route queries appropriately.
- `kb_name` parameter in `retrieve_knowledge` tool and Qdrant `search()` enables filtering to a single knowledge base.
- Doc upload auto-creates the disk directory if it doesn't exist; filenames are deduplicated with a timestamp suffix.

### Mixed Retrieval (Dense + Sparse with RRF Fusion)

`vector_store.py` implements hybrid search via Qdrant's `query_points` API:
- **Dense path**: Semantic vector search (cosine distance on 4096-dim embeddings from `Qwen/Qwen3-Embedding-8B`).
- **Sparse path**: BM25-style keyword search using Qdrant's built-in IDF modifier. Text is tokenized locally (Chinese single-char + English words, MD5-hashed to integer indices, TF values).
- **RRF fusion**: Both paths use `Prefetch` with `limit=top_k*2`, then combined via `FusionQuery(fusion=Fusion.RRF)` for the final `top_k` results.
- Results are filtered by `score_threshold` (default 0.7) and optionally by `kb_name` via Qdrant `Filter`.

### Daily Usage Rate Limiting

`services/daily_usage.py` enforces a per-user daily call limit (default 100):
- In-memory dict keyed by user_id → (date, count), with per-user `asyncio.Lock` for thread safety.
- Counts are persisted to `backend/data/daily_usage.json` every 5 calls for crash recovery (at most 4 lost counts).
- Cross-day reset is automatic (compares date).
- Returns HTTP 429 when limit is exceeded.

### Message Feedback System

`api/feedback.py` + `services/feedback.py` + `models/feedback.py`:
- `POST /feedback`: Upsert a `like`/`dislike` rating on a message. Toggle behavior — same rating twice = cancel. Different rating = switch.
- `GET /feedback/summary?message_id=`: Returns aggregate like/dislike counts.
- Frontend renders like/dislike buttons below each AI message with visual feedback.
- `SessionMessageResponse` includes `user_rating` so the UI reflects the current state when loading history.

### RAG Evaluation Pipeline

`scripts/rag_eval.py` runs an automated evaluation against `test_dataset.json`:
1. Loads test cases (question + ground_truth + expected contexts).
2. Builds a fresh Agent (same as production) and invokes it for each question.
3. Extracts all tool call results (Agent may call `retrieve_knowledge` multiple times with different queries).
4. Parses the formatted retrieval results into structured chunks with scores.
5. Outputs to `evals/eval_results.json` for downstream analysis and manual eval report generation.

### Frontend Architecture (React SPA)

```
[Browser] ← react-router-dom → [Pages] → [api.ts fetch/SSE] → Vite proxy → FastAPI
                                       ↓
                              localStorage (JWT token, user info)
```

- **Routing**: `react-router-dom v7` — public routes (`/login`, `/register`) and protected routes (`/chat`, `/knowledge`) wrapped in `<ProtectedRoute>` which checks `localStorage.getItem('access_token')`.
- **Auth flow**: Login/Register → backend returns JWT → stored in localStorage → attached as `Authorization: Bearer <token>` header on every request via `api.ts`.
- **API client** (`lib/api.ts`): Generic `request<T>()` wrapper around `fetch()` with automatic JWT injection and JSON parsing. Separate `createSSEStream()` for SSE-based chat streaming with callbacks for `token`, `tool_call`, `tool_result`, `sources`, `error`, `done` events.
- **Chat streaming**: `POST /chat/invoke` returns `{thread_id, session_id}` → `GET /chat/stream/{thread_id}` via SSE → renders tokens incrementally via `useState` + `useEffect` with `AbortController` for stop support. Tool calls are displayed as intermediate UI states.
- **UI components**: shadcn/ui primitives (Radix-based) + Tailwind CSS v4 + lucide-react icons. `@` path alias maps to `src/`.
- **Dev proxy**: Vite dev server proxies `/api/*` → `http://127.0.0.1:7500` (strips `/api` prefix). No CORS issues in development.

### Agent Building

`agents/builder.py` uses `create_agent()` (LangChain) to construct a LangGraph agent with:
- LLM (ChatOpenAI, configured via .env)
- `retrieve_knowledge` tool (LangChain @tool wrapping embed + vector search with optional `kb_name` filter)
- Optional AIOMySQLSaver checkpointer (from `langgraph-checkpoint-mysql[aiomysql]`) for conversation state
- **Dynamic KB injection**: On every agent build, queries `knowledge_bases` table and injects the KB list (name + description + keywords) into the system prompt, so the agent knows which knowledge bases exist and can route queries via `kb_name`
- Fallback system prompt is used when no knowledge bases exist
- System prompt enforces knowledge-only answers with source citations

### Key Design Decisions

- **Agentic RAG**: `retrieval_tool.py` wraps vector search as a LangChain `@tool`. The LLM decides when to retrieve, avoiding unnecessary embedding calls for non-knowledge queries. Query is capped at 500 characters. Tool accepts optional `kb_name` for multi-KB routing.
- **Dual storage**: MySQL stores document metadata (status, md5 hash, chunk count) and knowledge base metadata (name, description, keywords); Qdrant stores vectors and chunk content with `kb_name` payload for filtered search. Deletion removes from both.
- **Idempotent init**: `init_kb.py` computes MD5 per file, skips existing hashes in MySQL.
- **Async throughout**: SQLAlchemy async session, AsyncOpenAI, AsyncQdrantClient, asyncio task/queue for streaming.
- **Config via .env**: All infra endpoints, keys, and model names in `config.py` via `pydantic-settings`.
- **Singleton clients**: Embedding, Qdrant, ChatOpenAI, and checkpointer are lazily initialized singletons.
- **Markdown chunking**: Two-pass — first by `##`/`###` headers (preserving section metadata), then recursive split for long sections (chunk_size=400, overlap=50).
- **Embedding batch via gather**: `embed_batch()` uses `asyncio.gather` with per-item retry.
- **Mixed retrieval**: Qdrant `query_points` with dual `Prefetch` (dense cosine + sparse BM25) combined via `RRF fusion` for higher recall.
- **Dynamic agent prompt**: Agent system prompt is rebuilt on every invocation by querying `knowledge_bases`, enabling awareness of available KBs.
- **Per-user rate limiting**: In-memory dict with disk persistence, per-user locks, automatic cross-day reset.
- **Toggle feedback**: Same rating twice = cancel; different rating = switch; matches modern UX patterns (like Medium claps, YouTube dislikes).
- **No tests**: The project currently has no test suite.

### Full-Stack Development Workflow

1. Start backend: `cd backend && uv run uvicorn main:app --reload --host 0.0.0.0 --port 7500`
2. Start frontend (separate terminal): `cd frontend && pnpm dev` (port 5173)
3. Frontend proxies `/api/*` to backend, so open `http://localhost:5173` in browser.
4. To initialize knowledge base: `cd backend && uv run python -m app.scripts.init_kb`

### Project Context

This is an AI 智能客服系统 (AI-Powered Customer Service System) — a school assignment project implementing a full RAG (Retrieval-Augmented Generation) pipeline with Agentic AI capabilities. The sample knowledge base (`knowledges/auperator/`) contains product documentation for the fictional "Auperator" intelligent operations system.

### Dependencies

- **MySQL** + **Qdrant** as external services (configured via .env)
- **OpenAI-compatible** API for chat model
- **SiliconFlow** (or any OpenAI-compatible) API for embeddings (e.g., `Qwen/Qwen3-Embedding-8B`, 4096-dim)
- **LangChain** for text splitters, tool definition, and agent creation
- **LangGraph** for agent orchestration with checkpointing
- **FastAPI** + **uvicorn** for the web server
- **SQLAlchemy** (async) + **aiomysql** for the ORM
