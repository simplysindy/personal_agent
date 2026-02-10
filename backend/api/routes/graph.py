"""Graph visualization API routes."""

from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.knowledge.graph_store import GraphStore


router = APIRouter(prefix="/graph", tags=["graph"])

# Global store instance
_graph_store: Optional[GraphStore] = None


def set_store(graph_store: GraphStore) -> None:
    """Set the graph store instance."""
    global _graph_store
    _graph_store = graph_store


class GraphNode(BaseModel):
    """Node for visualization."""

    id: str
    label: str
    name: str
    type: str = ""
    properties: dict = {}


class GraphEdge(BaseModel):
    """Edge for visualization."""

    source: str
    target: str
    type: str


class GraphData(BaseModel):
    """Graph visualization data."""

    nodes: List[GraphNode]
    edges: List[GraphEdge]


class PathResponse(BaseModel):
    """Path between nodes response."""

    paths: List[List[dict]]
    found: bool


@router.get("/visualization", response_model=GraphData)
async def get_visualization_data(
    limit: int = Query(100, ge=10, le=500, description="Maximum nodes to return"),
    center_node: Optional[str] = Query(None, description="Center graph on this node ID"),
) -> GraphData:
    """
    Get graph data for visualization.

    Returns nodes and edges formatted for react-force-graph.
    """
    if not _graph_store:
        raise HTTPException(status_code=503, detail="Graph store not initialized")

    try:
        if center_node:
            # Get subgraph around center node
            return await _get_centered_graph(center_node, limit)
        else:
            # Get general overview
            data = _graph_store.get_graph_visualization_data(limit=limit)

            nodes = []
            for n in data.get("nodes", []):
                if n.get("id"):
                    nodes.append(GraphNode(
                        id=n["id"],
                        label=n.get("label", "Unknown"),
                        name=n.get("name", "Unknown"),
                        type=n.get("label", ""),
                    ))

            edges = []
            for e in data.get("edges", []):
                if e.get("source") and e.get("target"):
                    edges.append(GraphEdge(
                        source=e["source"],
                        target=e["target"],
                        type=e.get("type", "RELATED"),
                    ))

            return GraphData(nodes=nodes, edges=edges)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def _get_centered_graph(center_id: str, limit: int) -> GraphData:
    """Get subgraph centered on a specific node."""
    nodes = []
    edges = []
    seen_nodes = set()

    # Get center node
    center = _graph_store.get_document(center_id)
    if not center:
        # Try searching
        results = _graph_store.search_nodes(center_id)
        if results:
            center = results[0]["node"]
            center_id = center.get("id")

    if center:
        seen_nodes.add(center_id)
        nodes.append(GraphNode(
            id=center_id,
            label="center",
            name=center.get("title") or center.get("name") or "Unknown",
            type="center",
            properties=center,
        ))

        # Get neighbors
        neighbors = _graph_store.get_neighbors(center_id, depth=2)

        for neighbor in neighbors[:limit - 1]:
            n = neighbor["node"]
            n_id = n.get("id")

            if n_id and n_id not in seen_nodes:
                seen_nodes.add(n_id)
                nodes.append(GraphNode(
                    id=n_id,
                    label=neighbor.get("relationship", "related"),
                    name=n.get("title") or n.get("name") or "Unknown",
                    type=neighbor.get("relationship", ""),
                ))

                edges.append(GraphEdge(
                    source=center_id,
                    target=n_id,
                    type=neighbor.get("relationship", "RELATED"),
                ))

    return GraphData(nodes=nodes, edges=edges)


@router.get("/node/{node_id}")
async def get_node(node_id: str) -> dict:
    """Get detailed information about a node."""
    if not _graph_store:
        raise HTTPException(status_code=503, detail="Graph store not initialized")

    # Try document first
    doc = _graph_store.get_document(node_id)
    if doc:
        return {"type": "Document", "data": doc}

    # Search for the node
    results = _graph_store.search_nodes(node_id)
    if results:
        return {"type": results[0]["label"], "data": results[0]["node"]}

    raise HTTPException(status_code=404, detail="Node not found")


@router.get("/paths", response_model=PathResponse)
async def find_paths(
    from_id: str = Query(..., description="Source node ID or name"),
    to_id: str = Query(..., description="Target node ID or name"),
    max_hops: int = Query(3, ge=1, le=5, description="Maximum path length"),
) -> PathResponse:
    """Find paths between two nodes."""
    if not _graph_store:
        raise HTTPException(status_code=503, detail="Graph store not initialized")

    # Resolve node IDs if names were provided
    from_results = _graph_store.search_nodes(from_id)
    to_results = _graph_store.search_nodes(to_id)

    if not from_results:
        raise HTTPException(status_code=404, detail=f"Source node not found: {from_id}")
    if not to_results:
        raise HTTPException(status_code=404, detail=f"Target node not found: {to_id}")

    source_id = from_results[0]["node"].get("id")
    target_id = to_results[0]["node"].get("id")

    if not source_id or not target_id:
        raise HTTPException(status_code=500, detail="Could not get node IDs")

    paths = _graph_store.find_paths(source_id, target_id, max_hops=max_hops)

    return PathResponse(paths=paths, found=len(paths) > 0)


@router.get("/neighbors/{node_id}")
async def get_neighbors(
    node_id: str,
    depth: int = Query(1, ge=1, le=3, description="Depth to traverse"),
) -> List[dict]:
    """Get neighboring nodes."""
    if not _graph_store:
        raise HTTPException(status_code=503, detail="Graph store not initialized")

    # Resolve node ID if name was provided
    if len(node_id) != 16:  # Likely a name, not an ID
        results = _graph_store.search_nodes(node_id)
        if results:
            node_id = results[0]["node"].get("id")

    neighbors = _graph_store.get_neighbors(node_id, depth=depth)

    return [
        {
            "id": n["node"].get("id"),
            "name": n["node"].get("name") or n["node"].get("title"),
            "relationship": n.get("relationship"),
            "properties": n["node"],
        }
        for n in neighbors
    ]


@router.get("/stats")
async def get_graph_stats() -> dict:
    """Get graph statistics."""
    if not _graph_store:
        raise HTTPException(status_code=503, detail="Graph store not initialized")

    return _graph_store.get_graph_stats()
