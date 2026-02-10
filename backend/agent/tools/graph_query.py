"""Graph query tool for Cypher queries."""

from typing import Optional
from langchain_core.tools import tool

from backend.knowledge.graph_store import GraphStore


# Global store instance
_graph_store: Optional[GraphStore] = None


def set_graph_store(store: GraphStore) -> None:
    """Set the graph store instance."""
    global _graph_store
    _graph_store = store


@tool
def graph_query_tool(query: str) -> str:
    """
    Search the knowledge graph for entities and relationships.

    Use this tool to find information in the knowledge graph about:
    - Documents and notes
    - Projects
    - Concepts and topics
    - People mentioned
    - Connections between entities

    Args:
        query: Natural language query about what to find in the graph

    Returns:
        Formatted results from the graph search
    """
    if not _graph_store:
        return "Graph store not initialized"

    try:
        # Search for matching nodes
        results = _graph_store.search_nodes(query)

        if not results:
            return f"No results found for: {query}"

        # Format results
        output_parts = []
        for result in results[:10]:
            node = result["node"]
            label = result["label"]

            parts = [f"[{label}]"]
            if "title" in node:
                parts.append(f"Title: {node['title']}")
            if "name" in node:
                parts.append(f"Name: {node['name']}")
            if "summary" in node:
                parts.append(f"Summary: {node['summary'][:200]}...")
            if "definition" in node:
                parts.append(f"Definition: {node['definition']}")
            if "file_path" in node:
                parts.append(f"Path: {node['file_path']}")

            output_parts.append("\n".join(parts))

        return "\n\n---\n\n".join(output_parts)

    except Exception as e:
        return f"Error querying graph: {e}"


@tool
def find_connections_tool(entity1: str, entity2: str) -> str:
    """
    Find paths and connections between two entities in the knowledge graph.

    Use this tool when exploring how two concepts, documents, or people are connected.

    Args:
        entity1: First entity to find connections from
        entity2: Second entity to find connections to

    Returns:
        Paths and relationships connecting the two entities
    """
    if not _graph_store:
        return "Graph store not initialized"

    try:
        # Search for both entities
        results1 = _graph_store.search_nodes(entity1)
        results2 = _graph_store.search_nodes(entity2)

        if not results1:
            return f"Could not find entity: {entity1}"
        if not results2:
            return f"Could not find entity: {entity2}"

        # Get IDs
        id1 = results1[0]["node"].get("id")
        id2 = results2[0]["node"].get("id")

        if not id1 or not id2:
            return "Could not get entity IDs"

        # Find paths
        paths = _graph_store.find_paths(id1, id2, max_hops=3)

        if not paths:
            return f"No direct connection found between {entity1} and {entity2}"

        # Format paths
        output_parts = []
        for i, path in enumerate(paths, 1):
            path_names = []
            for node in path:
                name = node.get("name") or node.get("title") or "?"
                path_names.append(name)
            output_parts.append(f"Path {i}: {' -> '.join(path_names)}")

        return "\n".join(output_parts)

    except Exception as e:
        return f"Error finding connections: {e}"


@tool
def get_neighbors_tool(entity: str, depth: int = 1) -> str:
    """
    Get neighboring entities connected to a specific entity.

    Use this to explore what's connected to a particular concept, document, or person.

    Args:
        entity: The entity to find neighbors for
        depth: How many hops away to look (1-3)

    Returns:
        List of connected entities and their relationships
    """
    if not _graph_store:
        return "Graph store not initialized"

    try:
        # Find the entity
        results = _graph_store.search_nodes(entity)

        if not results:
            return f"Could not find entity: {entity}"

        node_id = results[0]["node"].get("id")
        if not node_id:
            return "Could not get entity ID"

        # Get neighbors
        depth = min(max(depth, 1), 3)  # Clamp between 1 and 3
        neighbors = _graph_store.get_neighbors(node_id, depth=depth)

        if not neighbors:
            return f"No neighbors found for {entity}"

        # Format output
        output_parts = []
        for neighbor in neighbors[:15]:
            node = neighbor["node"]
            rel = neighbor.get("relationship", "connected to")
            name = node.get("name") or node.get("title") or "Unknown"
            output_parts.append(f"- {rel}: {name}")

        return f"Entities connected to '{entity}':\n" + "\n".join(output_parts)

    except Exception as e:
        return f"Error getting neighbors: {e}"
