"""Retrieve node - fetches relevant context from knowledge stores."""

import re
from typing import Any
from collections import defaultdict

from backend.agent.state import AgentState, RetrievedContext
from backend.knowledge.graph_store import GraphStore
from backend.knowledge.vector_store import VectorStore


# Global store instances (will be initialized by the graph)
_graph_store: GraphStore = None
_vector_store: VectorStore = None


def set_stores(graph_store: GraphStore, vector_store: VectorStore) -> None:
    """Set the store instances for retrieval."""
    global _graph_store, _vector_store
    _graph_store = graph_store
    _vector_store = vector_store


def _is_folder_structure_query(query: str, entities: list[str]) -> tuple[bool, str]:
    """Detect if query is about folder/project structure."""
    query_lower = query.lower()

    # Keywords indicating folder structure query
    folder_keywords = [
        "folder", "arrange", "rearrange", "organize", "structure",
        "files in", "what's in", "what is in", "contents of", "list", "hierarchy",
        "project structure", "how is", "what documents", "project",
        "show me", "documents in", "notes in"
    ]

    # Words to strip from project names (include plurals)
    noise_words = ["folder", "folders", "project", "projects", "directory", "directories", "dir", "files", "file", "documents", "document"]

    for keyword in folder_keywords:
        if keyword in query_lower:
            # Try to extract project name from entities
            for entity in entities:
                if entity and len(entity) > 1:
                    # Clean up the entity - remove noise words using word boundaries
                    project_name = entity
                    for noise in noise_words:
                        project_name = re.sub(rf'\b{noise}\b', '', project_name, flags=re.IGNORECASE)
                    project_name = project_name.strip()
                    # Only return if there's a meaningful project name left
                    if project_name and len(project_name) > 1:
                        return True, project_name

            # Try to extract project name from query
            # Look for capitalized words that might be project names
            words = re.findall(r'\b[A-Z][A-Za-z]*\b', query)
            # Filter out common words
            filtered_words = [w for w in words if w.lower() not in noise_words and len(w) > 1]
            if filtered_words:
                return True, filtered_words[0]

            return True, ""

    return False, ""


def _get_folder_contents(project_name: str) -> list[RetrievedContext]:
    """Get folder contents as context."""
    context = []

    if not _graph_store:
        return context

    try:
        # Get all projects if no specific project
        if not project_name:
            projects = _graph_store.get_all_projects()
            if projects:
                project_list = "\n".join(
                    f"- {p.get('name', 'Unknown')}/ ({p.get('document_count', 0)} documents)"
                    for p in projects
                )
                context.append(RetrievedContext(
                    source="folder_structure",
                    content=f"Projects in vault:\n{project_list}",
                    metadata={"type": "project_list"},
                    score=1.0,
                ))
            return context

        # Get documents for specific project
        query = """
        MATCH (d:Document)-[:PART_OF]->(p:Project)
        WHERE toLower(p.name) CONTAINS toLower($project_name)
        RETURN d.title as title, d.file_path as file_path,
               d.file_type as file_type, d.summary as summary,
               p.name as project_name
        ORDER BY d.file_path
        """
        results = _graph_store.execute_cypher(query, {"project_name": project_name})

        if not results:
            # Try direct file path search
            query2 = """
            MATCH (d:Document)
            WHERE toLower(d.file_path) STARTS WITH toLower($project_name)
            RETURN d.title as title, d.file_path as file_path,
                   d.file_type as file_type, d.summary as summary
            ORDER BY d.file_path
            """
            results = _graph_store.execute_cypher(query2, {"project_name": project_name})

        if results:
            # Group by type
            by_type = defaultdict(list)
            for doc in results:
                file_type = doc.get("file_type", "unknown")
                by_type[file_type].append(doc)

            # Format folder structure
            content_parts = [f"Contents of '{project_name}' folder:\n"]
            content_parts.append(f"Total: {len(results)} documents\n")

            for file_type, docs in sorted(by_type.items()):
                type_icon = {
                    "markdown": "MD",
                    "pdf": "PDF",
                    "docx": "DOC",
                    "pptx": "PPT",
                    "image": "IMG",
                }.get(file_type, "?")
                content_parts.append(f"\n{type_icon} files ({len(docs)}):")
                for doc in docs:
                    title = doc.get("title", "Untitled")
                    path = doc.get("file_path", "")
                    summary = doc.get("summary", "")[:100] if doc.get("summary") else ""
                    content_parts.append(f"  - {title}")
                    if summary:
                        content_parts.append(f"    {summary}...")

            context.append(RetrievedContext(
                source="folder_structure",
                content="\n".join(content_parts),
                metadata={"type": "folder_contents", "project": project_name},
                score=1.0,
            ))

            # Also get key concepts for this project
            concept_query = """
            MATCH (d:Document)-[:PART_OF]->(p:Project)
            WHERE toLower(p.name) CONTAINS toLower($project_name)
            MATCH (d)-[:MENTIONS]->(c:Concept)
            RETURN c.name as concept, count(d) as mentions
            ORDER BY mentions DESC
            LIMIT 10
            """
            concepts = _graph_store.execute_cypher(concept_query, {"project_name": project_name})

            if concepts:
                concept_list = "\n".join(
                    f"  - {c['concept']} ({c['mentions']} mentions)"
                    for c in concepts
                )
                context.append(RetrievedContext(
                    source="folder_structure",
                    content=f"Key topics in {project_name}:\n{concept_list}",
                    metadata={"type": "project_concepts"},
                    score=0.9,
                ))

    except Exception as e:
        print(f"Folder structure query error: {e}")

    return context


def retrieve_node(state: AgentState) -> dict[str, Any]:
    """
    Retrieve relevant context based on query and intent.

    This node:
    1. Checks for folder structure queries
    2. Performs vector search for semantic similarity
    3. Queries knowledge graph for entities and relationships
    4. Combines results into context for reasoning
    """
    query = state.query
    intent = state.intent
    entities = state.entities

    context = []

    # Check for folder structure queries first
    is_folder_query, project_name = _is_folder_structure_query(query, entities)
    if is_folder_query:
        folder_context = _get_folder_contents(project_name)
        context.extend(folder_context)
        # If we got good folder results, we can skip some vector search
        if folder_context:
            # Still do limited vector search for additional context
            pass

    # Vector search for relevant content
    if _vector_store:
        try:
            vector_results = _vector_store.search(query, n_results=5)

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

                    context.append(
                        RetrievedContext(
                            source="vector",
                            content=doc[:2000],  # Limit content length
                            metadata=metadata,
                            score=1.0 - distance,  # Convert distance to similarity
                        )
                    )
        except Exception as e:
            print(f"Vector search error: {e}")

    # Graph queries based on intent
    if _graph_store:
        try:
            # Search for entities in graph
            if entities:
                for entity in entities[:3]:  # Limit entities searched
                    results = _graph_store.search_nodes(entity)
                    for result in results[:2]:
                        node = result["node"]
                        context.append(
                            RetrievedContext(
                                source="graph",
                                content=_format_graph_node(node),
                                metadata={
                                    "label": result["label"],
                                    "id": node.get("id"),
                                },
                                score=0.8,
                            )
                        )

            # For explore intent, get graph neighbors
            if intent == "explore" and context:
                for ctx in context[:2]:
                    if ctx.source == "graph" and ctx.metadata.get("id"):
                        neighbors = _graph_store.get_neighbors(ctx.metadata["id"], depth=1)
                        for neighbor in neighbors[:3]:
                            context.append(
                                RetrievedContext(
                                    source="graph",
                                    content=_format_graph_node(neighbor["node"]),
                                    metadata={
                                        "relationship": neighbor.get("relationship"),
                                    },
                                    score=0.6,
                                )
                            )

            # For reasoning, try to find paths between entities
            if intent == "reason" and len(entities) >= 2:
                # Try to find paths between first two entities
                results1 = _graph_store.search_nodes(entities[0])
                results2 = _graph_store.search_nodes(entities[1])

                if results1 and results2:
                    id1 = results1[0]["node"].get("id")
                    id2 = results2[0]["node"].get("id")

                    if id1 and id2:
                        paths = _graph_store.find_paths(id1, id2, max_hops=3)
                        for path in paths[:2]:
                            path_text = " -> ".join(
                                node.get("name", node.get("title", "?")) for node in path
                            )
                            context.append(
                                RetrievedContext(
                                    source="graph",
                                    content=f"Connection path: {path_text}",
                                    metadata={"path": True},
                                    score=0.9,
                                )
                            )

        except Exception as e:
            print(f"Graph query error: {e}")

    # Sort by score and deduplicate
    context = _deduplicate_context(context)
    context.sort(key=lambda x: x.score, reverse=True)

    return {
        "context": context[:10],  # Limit total context
    }


def _format_graph_node(node: dict) -> str:
    """Format a graph node for context."""
    parts = []

    if "title" in node:
        parts.append(f"Title: {node['title']}")
    if "name" in node:
        parts.append(f"Name: {node['name']}")
    if "summary" in node:
        parts.append(f"Summary: {node['summary']}")
    if "description" in node:
        parts.append(f"Description: {node['description']}")
    if "definition" in node:
        parts.append(f"Definition: {node['definition']}")
    if "extracted_text" in node:
        text = node["extracted_text"][:500]
        parts.append(f"Content: {text}...")
    if "file_path" in node:
        parts.append(f"Source: {node['file_path']}")

    return "\n".join(parts)


def _deduplicate_context(context: list[RetrievedContext]) -> list[RetrievedContext]:
    """Remove duplicate context items."""
    seen = set()
    unique = []

    for ctx in context:
        # Use content hash for deduplication
        key = hash(ctx.content[:200])
        if key not in seen:
            seen.add(key)
            unique.append(ctx)

    return unique
