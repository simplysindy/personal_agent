# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Personal Knowledge Management AI Agent that indexes an Obsidian vault into a Neo4j knowledge graph and ChromaDB vector store, then exposes a LangGraph-powered conversational agent over a FastAPI backend.

## Commands

```bash
# Start Neo4j (required before running backend)
docker compose -f docker/docker-compose.yml up -d

# Install dependencies
uv sync

# Run initial vault extraction (interactive, prompts for confirmation)
uv run python scripts/init_extraction.py

# Start the API server (with hot reload)
uv run python -m backend.main

# Serve the frontend (static HTML/JS on port 5173)
uv run python scripts/serve_frontend.py

# Test the agent interactively
uv run python scripts/test_agent.py

# Lint
uv run ruff check backend/ scripts/

# Run tests
uv run pytest
```

## Architecture

### Agent (LangGraph)

`backend/agent/graph.py` defines a 4-node LangGraph state machine:

```
understand → retrieve → reason ─┐
                  ↑              │ (loop if more info needed, max 3 steps)
                  └──────────────┘
                                 └─→ respond → END
```

- **understand** — LLM-based intent classification (search/explore/add/summarize/reason/general) and entity extraction. Falls back to keyword matching.
- **retrieve** — Dual retrieval: ChromaDB vector search + Neo4j graph queries. Has special handling for folder-structure queries.
- **reason** — LLM call with intent-specific prompt templates. Includes conversation history for multi-turn context. Can request additional retrieval loops.
- **respond** — Formats final response, appends source citations.

State is defined in `backend/agent/state.py` (`AgentState` Pydantic model with LangGraph message annotations).

### Knowledge Stores

- **Neo4j** (`backend/knowledge/graph_store.py`) — Graph database with node types: Document, Project, Concept, Person, Resource, Image. Relationships: PART_OF, MENTIONS, LINKS_TO, RELATES_TO, CONTAINS_IMAGE.
- **ChromaDB** (`backend/knowledge/vector_store.py`) — Vector store using cosine similarity. Stores both full documents and overlapping text chunks (1000 char, 200 overlap).
- **Models** (`backend/knowledge/models.py`) — Pydantic entities with deterministic MD5-based IDs.

### Extraction Pipeline

`backend/extraction/pipeline.py` orchestrates file processing:

1. Parsers (`backend/extraction/parsers/`) — Markdown (with frontmatter/wikilink extraction), PDF (with image extraction via PyMuPDF), DOCX, PPTX, Image (OCR via pytesseract + optional vision LLM).
2. Extractors — NLP via spaCy (`en_core_web_sm`) for named entities/technologies; LLM via OpenRouter for summaries and concept extraction.
3. Storage — Writes to both Neo4j (nodes + relationships) and ChromaDB (embeddings + chunks).

File watcher (`backend/extraction/watcher.py`) uses `watchdog` for incremental vault sync.

### API Layer

FastAPI app (`backend/main.py`) with route modules under `backend/api/routes/`:
- `/api/chat/message` (POST) and `/api/chat/ws` (WebSocket) — Agent interaction
- `/api/search/` — Hybrid vector+graph search
- `/api/knowledge/` — CRUD for concepts, people, resources, projects
- `/api/graph/` — Visualization data, path finding, neighbors
- `/api/sync/` — Full vault sync, single-file sync, file watcher start/stop

### LLM Access

All LLM calls go through OpenRouter (`openrouter.ai/api/v1`) using raw `httpx` requests (not LangChain LLM wrappers). Model configured via `OPENROUTER_MODEL` in `.env`.

### Configuration

`backend/config.py` uses `pydantic-settings` to load from `.env`. Key settings: OpenRouter API key/model, Neo4j connection, ChromaDB collection name, embedding model (`all-MiniLM-L6-v2`), spaCy model, API host/port, vault path.

### Frontend

Minimal static HTML + vanilla JS (`frontend/index.html`, `frontend/app.js`). Served via a simple Python HTTP server on port 5173.

## Key Patterns

- Store instances are injected via module-level `set_*()` functions (not dependency injection). The `main.py` lifespan handler wires everything at startup.
- Agent tools in `backend/agent/tools/` are decorated with `@tool` from LangChain but currently invoked directly by nodes rather than via a tool-calling LLM.
- Ruff config: line length 100, target Python 3.11, rules E/F/I/N/W, E501 ignored.
