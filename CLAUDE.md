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

# Interactive retrieval test
cd backend && uv run python -m app.scripts.test_retrieval

# Install / sync dependencies
cd backend && uv sync

# Activate venv
source backend/.venv/bin/activate
```

## Project Structure

```
simple-rag/
├── backend/
│   ├── app/
│   │   ├── api/           # FastAPI route handlers (auth, knowledge)
│   │   │   ├── auth.py        # POST /auth/register, /auth/login, GET /auth/me
│   │   │   ├── knowledge.py   # GET/POST/DELETE /knowledge/*
│   │   │   └── deps.py        # JWT auth dependency (get_current_user)
│   │   ├── core/          # Infrastructure layer
│   │   │   ├── config.py      # pydantic-settings (.env based)
│   │   │   ├── database.py    # SQLAlchemy async engine + session (MySQL)
│   │   │   └── security.py    # bcrypt hash, JWT create/decode
│   │   ├── models/        # SQLAlchemy ORM models
│   │   │   ├── user.py        # users table
│   │   │   ├── knowledge_doc.py # knowledge_docs table
│   │   │   └── session.py     # sessions table
│   │   ├── schemas/       # Pydantic request/response models
│   │   ├── services/      # Business logic layer
│   │   │   ├── user.py           # register / login / get_user_by_id
│   │   │   ├── knowledge.py      # document CRUD + process pipeline
│   │   │   ├── document_parser.py # parse_document() dispatcher (.md vs .txt)
│   │   │   ├── text_splitter.py   # MarkdownHeaderTextSplitter + RecursiveCharacterTextSplitter
│   │   │   ├── embedding.py      # OpenAI-compatible embedding API (single + batch)
│   │   │   ├── vector_store.py   # Qdrant CRUD (ensure_collection, upsert, search, delete)
│   │   │   └── retrieval_tool.py # LangChain Tool wrapping embed + search for agentic RAG
│   │   └── scripts/       # CLI tools
│   │       ├── init_kb.py        # Batch init: scan → dedup → parse → embed → store
│   │       └── test_retrieval.py # Interactive CLI for testing retrieval
│   ├── main.py            # FastAPI app entry, lifespan (auto-create tables), CORS, router registration
│   ├── pyproject.toml     # Python deps (uv)
│   └── .env.example       # Required env vars (copy to .env)
└── knowledges/            # Knowledge base documents (the "source of truth")
    └── auperator/         # Product docs for the Auperator intelligent ops system
```

## Architecture

### Layered Pattern (FastAPI)

API routes (`api/`) call services (`services/`), which use models (`models/`) and core infra (`core/`). Services are the business logic layer — keep them free of HTTP concerns.

### RAG Pipeline

```
file upload → parse_document() → split into chunks → embed_batch() → upsert to Qdrant
     ↓
MySQL record (KnowledgeDoc) created with status tracking
```

### Key Design Decisions

- **Agentic RAG**: `retrieval_tool.py` wraps vector search as a LangChain `@tool`, letting the LLM decide when to retrieve. This avoids unnecessary embedding calls for non-knowledge queries.
- **Dual storage**: MySQL stores document metadata (status, hash, chunk count); Qdrant stores vectors and chunk content. Deletion removes from both.
- **Idempotent init**: `init_kb.py` checks MD5 against existing MySQL records before processing.
- **Async throughout**: SQLAlchemy async session, AsyncOpenAI, AsyncQdrantClient.
- **Config via .env**: All infra endpoints, keys, and model names in `config.py` via `pydantic-settings`.
- **Package manager**: uv (fast Python package manager), with deps in `pyproject.toml`.
- **Markdown chunking**: Two-pass — first by `##`/`###` headers (preserving section metadata), then recursive split for long sections (chunk_size=400, overlap=50).

### Dependencies

- **MySQL** + **Qdrant** as external services (configured via .env)
- **OpenAI-compatible** API for chat model
- **SiliconFlow** (or any OpenAI-compatible) API for embeddings (e.g., `Qwen/Qwen3-Embedding-8B`, 4096-dim)
- **LangChain** for text splitters and tool definition
- **FastAPI** + **uvicorn** for the web server
- **SQLAlchemy** (async) + **aiomysql** for the ORM
