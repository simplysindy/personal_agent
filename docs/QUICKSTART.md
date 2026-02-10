# Quick Start Guide

Detailed setup, configuration, usage, and troubleshooting for the Personal Knowledge Agent.

## Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| **Docker** | 20.10+ | For running Neo4j |
| **Python** | 3.11+ | Required by LangGraph and type annotations |
| **uv** | Latest | Python package manager ([install](https://docs.astral.sh/uv/getting-started/installation/)) |
| **Tesseract** | 5.0+ | For OCR on images (optional) |
| **Obsidian vault** | Any | A folder of Markdown/PDF/DOCX/PPTX files to index |

### Installing prerequisites

**macOS:**

```bash
brew install uv tesseract
```

**Ubuntu/Debian:**

```bash
# uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Tesseract (for OCR)
sudo apt install tesseract-ocr
```

---

## Step-by-Step Setup

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/personal-agent.git
cd personal-agent
```

### 2. Start Neo4j via Docker Compose

```bash
docker compose -f docker/docker-compose.yml up -d
```

This starts Neo4j 5.17 Community with:
- **Bolt protocol** on port `7687` (used by the app)
- **HTTP browser** on port `7474` (for manual exploration)
- Default credentials: `neo4j` / `password123`
- APOC plugin enabled

Wait for the health check to pass:

```bash
docker compose -f docker/docker-compose.yml ps
# Should show "healthy" status
```

### 3. Install Python dependencies

```bash
uv sync
```

This installs all dependencies from `pyproject.toml` into a virtual environment managed by uv.

### 4. Download the spaCy model

```bash
uv run python -m spacy download en_core_web_sm
```

This model is used for named entity recognition (people, organizations, technologies).

### 5. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and set at minimum:

```env
OPENROUTER_API_KEY=your_key_here   # Get one at https://openrouter.ai/keys
VAULT_PATH=path/to/your/vault       # Relative or absolute path to your Obsidian vault
```

### 6. Run initial extraction

```bash
uv run python scripts/init_extraction.py
```

This scans your vault, extracts content from all supported files, and populates both Neo4j and ChromaDB. The script is interactive and will show you vault statistics before asking for confirmation.

### 7. Start the API server

```bash
uv run python -m backend.main
```

The server starts on `http://localhost:8000` with hot reload enabled. You'll see:

```
Initializing knowledge stores...
Initializing agent...
Initializing extraction pipeline...
Application started successfully!
```

### 8. Serve the frontend

In a separate terminal:

```bash
uv run python scripts/serve_frontend.py
```

Open `http://localhost:5173` in your browser.

---

## Configuration Reference

All settings are loaded from `.env` via `pydantic-settings` (`backend/config.py`).

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENROUTER_API_KEY` | *(required)* | API key from [OpenRouter](https://openrouter.ai/keys) |
| `OPENROUTER_MODEL` | `openai/gpt-5.2-chat` | LLM model for intent classification and reasoning |
| `OPENROUTER_VISION_MODEL` | `openai/gpt-5.2-chat` | Vision model for image description |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | OpenRouter API base URL |
| `NEO4J_URI` | `bolt://localhost:7687` | Neo4j Bolt connection URI |
| `NEO4J_USER` | `neo4j` | Neo4j username |
| `NEO4J_PASSWORD` | `password123` | Neo4j password |
| `VAULT_PATH` | `Obsidian-Neo4j` | Path to your Obsidian vault |
| `CHROMA_PATH` | `data/chroma` | ChromaDB persistence directory |
| `CHROMA_COLLECTION_NAME` | `obsidian_notes` | ChromaDB collection name |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | sentence-transformers model for embeddings |
| `SPACY_MODEL` | `en_core_web_sm` | spaCy model for NER |
| `API_HOST` | `0.0.0.0` | API server bind address |
| `API_PORT` | `8000` | API server port |
| `CORS_ORIGINS` | `["http://localhost:5173", "http://localhost:3000"]` | Allowed CORS origins (JSON array) |

---

## Usage Guide

### Chat Interface

The web UI at `http://localhost:5173` provides a chat interface. Type natural language questions about your vault:

- *"What do I know about distributed systems?"* — semantic search
- *"How are Kafka and Redis related in my notes?"* — graph exploration
- *"Summarize my machine learning project"* — content summarization
- *"Remember that gRPC uses HTTP/2 for transport"* — add knowledge

### API Examples

**Send a chat message:**

```bash
curl -X POST http://localhost:8000/api/chat/message \
  -H "Content-Type: application/json" \
  -d '{"message": "What concepts are related to distributed systems?"}'
```

### Neo4j Browser

Visit `http://localhost:7474` to explore the graph directly with Cypher:

```cypher
-- See all node types and counts
CALL {
    MATCH (d:Document) RETURN 'Document' as label, count(d) as count
    UNION ALL
    MATCH (c:Concept) RETURN 'Concept' as label, count(c) as count
    UNION ALL
    MATCH (p:Person) RETURN 'Person' as label, count(p) as count
}
RETURN label, count

-- Find documents about a topic
MATCH (d:Document)-[:MENTIONS]->(c:Concept)
WHERE c.name CONTAINS 'distributed'
RETURN d.title, c.name

-- Explore connections between two concepts
MATCH path = shortestPath(
    (a:Concept {name: 'Kafka'})-[*1..4]-(b:Concept {name: 'Redis'})
)
RETURN path
```

---

## Development

### Linting

```bash
uv run ruff check backend/ scripts/
```

Ruff is configured in `pyproject.toml` with: line length 100, Python 3.11 target, rules E/F/I/N/W (E501 ignored).

### Testing

```bash
uv run pytest
```

### Interactive Agent Testing

```bash
uv run python scripts/test_agent.py
```

This starts an interactive REPL where you can send queries to the agent and see the full state machine execution.

### Adding a New Parser

1. Create a new parser class in `backend/extraction/parsers/`
2. Add the file extension mapping to `ExtractionPipeline.PARSERS` and `ExtractionPipeline.FILE_TYPES` in `backend/extraction/pipeline.py`
3. Add an `_extract_<format>()` method to `ExtractionPipeline`
4. Export the parser from `backend/extraction/parsers/__init__.py`

### Adding a New Intent

1. Add the intent literal to `AgentState.intent` in `backend/agent/state.py`
2. Update the LLM prompt in `backend/agent/nodes/understand.py`
3. Add intent-specific retrieval logic in `backend/agent/nodes/retrieve.py`
4. Add an intent-specific prompt template in `backend/agent/nodes/reason.py`