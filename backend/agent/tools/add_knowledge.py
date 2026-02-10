"""Tool for adding knowledge to the graph."""

import json
from typing import Optional
from langchain_core.tools import tool

from backend.knowledge.graph_store import GraphStore
from backend.knowledge.vector_store import VectorStore
from backend.knowledge.models import Concept, Person, Resource


# Global store instances
_graph_store: Optional[GraphStore] = None
_vector_store: Optional[VectorStore] = None


def set_stores(graph_store: GraphStore, vector_store: VectorStore) -> None:
    """Set the store instances."""
    global _graph_store, _vector_store
    _graph_store = graph_store
    _vector_store = vector_store


@tool
def add_knowledge_tool(
    name: str,
    description: str,
    knowledge_type: str = "concept",
    related_to: str = None,
) -> str:
    """
    Add new knowledge to the knowledge graph.

    Use this when the user wants to remember something or add a new concept.

    Args:
        name: Name of the concept, person, or resource
        description: Description or definition
        knowledge_type: Type of knowledge (concept, person, resource)
        related_to: Optional - name of related entity to link to

    Returns:
        Confirmation of what was added
    """
    if not _graph_store:
        return "Graph store not initialized"

    try:
        knowledge_type = knowledge_type.lower()

        if knowledge_type == "concept":
            entity = Concept(name=name, definition=description)
            _graph_store.upsert_concept(entity)

            # Also add to vector store for semantic search
            if _vector_store:
                _vector_store.add_document(
                    entity.id,
                    f"{name}: {description}",
                    {"title": name, "type": "concept"},
                )

            result = f"Added concept: {name}"

        elif knowledge_type == "person":
            entity = Person(name=name, role=description)
            _graph_store.upsert_person(entity)

            if _vector_store:
                _vector_store.add_document(
                    entity.id,
                    f"{name}: {description}",
                    {"title": name, "type": "person"},
                )

            result = f"Added person: {name}"

        elif knowledge_type == "resource":
            entity = Resource(name=name, description=description)
            _graph_store.upsert_resource(entity)

            if _vector_store:
                _vector_store.add_document(
                    entity.id,
                    f"{name}: {description}",
                    {"title": name, "type": "resource"},
                )

            result = f"Added resource: {name}"

        else:
            return f"Unknown knowledge type: {knowledge_type}. Use concept, person, or resource."

        # Create relationship if related_to specified
        if related_to:
            related_results = _graph_store.search_nodes(related_to)
            if related_results:
                related_id = related_results[0]["node"].get("id")
                related_label = related_results[0]["label"]

                if related_id:
                    _graph_store.create_relationship(
                        source_label=knowledge_type.capitalize(),
                        source_id=entity.id,
                        target_label=related_label,
                        target_id=related_id,
                        rel_type="RELATES_TO",
                    )
                    result += f"\nLinked to: {related_to}"

        return result

    except Exception as e:
        return f"Error adding knowledge: {e}"


@tool
def link_entities_tool(
    entity1: str,
    entity2: str,
    relationship: str = "RELATES_TO",
) -> str:
    """
    Create a relationship between two entities in the knowledge graph.

    Use this to connect concepts, documents, or people.

    Args:
        entity1: First entity name
        entity2: Second entity name
        relationship: Type of relationship (e.g., RELATES_TO, USES, WORKS_WITH)

    Returns:
        Confirmation of the link created
    """
    if not _graph_store:
        return "Graph store not initialized"

    try:
        # Find both entities
        results1 = _graph_store.search_nodes(entity1)
        results2 = _graph_store.search_nodes(entity2)

        if not results1:
            return f"Could not find entity: {entity1}"
        if not results2:
            return f"Could not find entity: {entity2}"

        id1 = results1[0]["node"].get("id")
        label1 = results1[0]["label"]
        id2 = results2[0]["node"].get("id")
        label2 = results2[0]["label"]

        if not id1 or not id2:
            return "Could not get entity IDs"

        # Create relationship
        _graph_store.create_relationship(
            source_label=label1,
            source_id=id1,
            target_label=label2,
            target_id=id2,
            rel_type=relationship.upper().replace(" ", "_"),
        )

        return f"Created link: {entity1} -[{relationship}]-> {entity2}"

    except Exception as e:
        return f"Error creating link: {e}"
