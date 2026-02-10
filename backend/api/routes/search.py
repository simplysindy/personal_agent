"""Search API routes."""

from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.knowledge.graph_store import GraphStore
from backend.knowledge.vector_store import VectorStore


router = APIRouter(prefix="/search", tags=["search"])

# Global store instances
_graph_store: Optional[GraphStore] = None
_vector_store: Optional[VectorStore] = None


def set_stores(graph_store: GraphStore, vector_store: VectorStore) -> None:
    """Set store instances."""
    global _graph_store, _vector_store
    _graph_store = graph_store
    _vector_store = vector_store


class SearchResult(BaseModel):
    """Individual search result."""

    id: str
    title: str
    content: str
    source: str
    file_type: Optional[str] = None
    score: float = 0.0
    metadata: dict = {}


class SearchResponse(BaseModel):
    """Search response."""

    query: str
    results: List[SearchResult]
    total: int


@router.get("/", response_model=SearchResponse)
async def search(
    q: str = Query(..., description="Search query"),
    type: Optional[str] = Query(None, description="Filter by type: vector, graph, or hybrid"),
    file_type: Optional[str] = Query(None, description="Filter by file type: md, pdf, docx, pptx"),
    limit: int = Query(10, ge=1, le=50, description="Number of results"),
) -> SearchResponse:
    """
    Search the knowledge base.

    - **q**: Search query
    - **type**: Search type (vector for semantic, graph for entity, hybrid for both)
    - **file_type**: Filter by file type
    - **limit**: Maximum results to return
    """
    results = []

    search_type = type or "hybrid"

    # Vector search
    if search_type in ("vector", "hybrid") and _vector_store:
        try:
            where = {"file_type": file_type} if file_type else None
            vector_results = _vector_store.search(q, n_results=limit, where=where)

            if vector_results and vector_results.get("documents"):
                for i, doc in enumerate(vector_results["documents"][0]):
                    metadata = (
                        vector_results["metadatas"][0][i]
                        if vector_results.get("metadatas")
                        else {}
                    )
                    distance = (
                        vector_results["distances"][0][i]
                        if vector_results.get("distances")
                        else 1.0
                    )

                    results.append(SearchResult(
                        id=vector_results["ids"][0][i] if vector_results.get("ids") else f"v_{i}",
                        title=metadata.get("title", "Untitled"),
                        content=doc[:500],
                        source="vector",
                        file_type=metadata.get("file_type"),
                        score=1.0 - distance,
                        metadata=metadata,
                    ))
        except Exception as e:
            print(f"Vector search error: {e}")

    # Graph search
    if search_type in ("graph", "hybrid") and _graph_store:
        try:
            graph_results = _graph_store.search_nodes(q)

            for result in graph_results[:limit]:
                node = result["node"]
                label = result["label"]

                title = node.get("title") or node.get("name") or "Unknown"
                content = (
                    node.get("summary")
                    or node.get("definition")
                    or node.get("extracted_text", "")[:500]
                    or ""
                )

                results.append(SearchResult(
                    id=node.get("id", ""),
                    title=title,
                    content=content,
                    source="graph",
                    file_type=node.get("file_type"),
                    score=0.8,  # Graph results get consistent score
                    metadata={"label": label, "file_path": node.get("file_path")},
                ))
        except Exception as e:
            print(f"Graph search error: {e}")

    # Sort by score and deduplicate
    seen_ids = set()
    unique_results = []
    for r in sorted(results, key=lambda x: x.score, reverse=True):
        if r.id not in seen_ids:
            seen_ids.add(r.id)
            unique_results.append(r)

    return SearchResponse(
        query=q,
        results=unique_results[:limit],
        total=len(unique_results),
    )


@router.get("/suggest")
async def suggest(
    q: str = Query(..., min_length=1, description="Partial query for suggestions"),
    limit: int = Query(5, ge=1, le=20),
) -> List[str]:
    """Get search suggestions based on partial query."""
    suggestions = set()

    if _graph_store:
        try:
            # Search for matching concepts and documents
            results = _graph_store.search_nodes(q)
            for result in results[:limit * 2]:
                node = result["node"]
                if "name" in node:
                    suggestions.add(node["name"])
                if "title" in node:
                    suggestions.add(node["title"])
        except Exception:
            pass

    return list(suggestions)[:limit]
