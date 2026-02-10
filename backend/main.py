"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.knowledge.graph_store import GraphStore
from backend.knowledge.vector_store import VectorStore
from backend.extraction.pipeline import ExtractionPipeline
from backend.agent import AgentGraph

from backend.api.routes import chat, search, knowledge, graph, sync


# Global instances
graph_store: GraphStore = None
vector_store: VectorStore = None
agent: AgentGraph = None
pipeline: ExtractionPipeline = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - initialize and cleanup resources."""
    global graph_store, vector_store, agent, pipeline

    # Initialize stores
    print("Initializing knowledge stores...")
    graph_store = GraphStore()
    graph_store.connect()
    graph_store.initialize_schema()

    vector_store = VectorStore()
    vector_store.connect()

    # Initialize agent
    print("Initializing agent...")
    agent = AgentGraph(graph_store, vector_store)
    agent.initialize()

    # Initialize extraction pipeline
    print("Initializing extraction pipeline...")
    pipeline = ExtractionPipeline(
        graph_store=graph_store,
        vector_store=vector_store,
        use_llm=True,
        use_vision=True,
    )

    # Set instances for routes
    chat.set_agent(agent)
    search.set_stores(graph_store, vector_store)
    knowledge.set_stores(graph_store, vector_store)
    graph.set_store(graph_store)
    sync.set_pipeline(pipeline)

    print("Application started successfully!")

    yield

    # Cleanup
    print("Shutting down...")
    if graph_store:
        graph_store.close()


# Create FastAPI app
app = FastAPI(
    title="Personal Agent API",
    description="Knowledge Management AI Agent for Obsidian Vault",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(chat.router, prefix="/api")
app.include_router(search.router, prefix="/api")
app.include_router(knowledge.router, prefix="/api")
app.include_router(graph.router, prefix="/api")
app.include_router(sync.router, prefix="/api")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Personal Agent API",
        "version": "0.1.0",
        "status": "running",
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    health_status = {
        "status": "healthy",
        "graph_store": graph_store is not None,
        "vector_store": vector_store is not None,
        "agent": agent is not None,
    }

    if graph_store:
        try:
            stats = graph_store.get_graph_stats()
            health_status["graph_nodes"] = sum(stats.values())
        except Exception:
            health_status["graph_store"] = False

    if vector_store:
        try:
            health_status["vector_docs"] = vector_store.count()
        except Exception:
            health_status["vector_store"] = False

    return health_status


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
    )
