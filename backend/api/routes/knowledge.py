"""Knowledge management API routes."""

from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.knowledge.graph_store import GraphStore
from backend.knowledge.vector_store import VectorStore
from backend.knowledge.models import Concept, Person, Resource


router = APIRouter(prefix="/knowledge", tags=["knowledge"])

# Global store instances
_graph_store: Optional[GraphStore] = None
_vector_store: Optional[VectorStore] = None


def set_stores(graph_store: GraphStore, vector_store: VectorStore) -> None:
    """Set store instances."""
    global _graph_store, _vector_store
    _graph_store = graph_store
    _vector_store = vector_store


# Request/Response Models
class ConceptCreate(BaseModel):
    """Create concept request."""

    name: str = Field(..., min_length=1)
    definition: str = ""
    aliases: List[str] = []
    related_to: Optional[str] = None


class PersonCreate(BaseModel):
    """Create person request."""

    name: str = Field(..., min_length=1)
    role: str = ""
    organization: str = ""


class ResourceCreate(BaseModel):
    """Create resource request."""

    name: str = Field(..., min_length=1)
    resource_type: str = ""
    url: str = ""
    description: str = ""


class EntityResponse(BaseModel):
    """Entity response."""

    id: str
    name: str
    type: str
    details: dict = {}


class ProjectResponse(BaseModel):
    """Project response."""

    id: str
    name: str
    folder_path: str
    description: str
    document_count: int


# Concept endpoints
@router.post("/concepts", response_model=EntityResponse)
async def create_concept(concept: ConceptCreate) -> EntityResponse:
    """Add a new concept to the knowledge graph."""
    if not _graph_store:
        raise HTTPException(status_code=503, detail="Graph store not initialized")

    entity = Concept(
        name=concept.name,
        definition=concept.definition,
        aliases=concept.aliases,
    )

    _graph_store.upsert_concept(entity)

    # Add to vector store
    if _vector_store:
        _vector_store.add_document(
            entity.id,
            f"{concept.name}: {concept.definition}",
            {"title": concept.name, "type": "concept"},
        )

    # Link to related entity if specified
    if concept.related_to:
        results = _graph_store.search_nodes(concept.related_to)
        if results:
            related_id = results[0]["node"].get("id")
            if related_id:
                _graph_store.link_concepts(entity.id, related_id)

    return EntityResponse(
        id=entity.id,
        name=entity.name,
        type="concept",
        details={"definition": entity.definition, "aliases": entity.aliases},
    )


@router.get("/concepts", response_model=List[EntityResponse])
async def list_concepts(
    limit: int = Query(50, ge=1, le=200),
) -> List[EntityResponse]:
    """List all concepts."""
    if not _graph_store:
        raise HTTPException(status_code=503, detail="Graph store not initialized")

    query = "MATCH (c:Concept) RETURN c LIMIT $limit"
    results = _graph_store.execute_cypher(query, {"limit": limit})

    return [
        EntityResponse(
            id=r["c"].get("id", ""),
            name=r["c"].get("name", ""),
            type="concept",
            details={
                "definition": r["c"].get("definition", ""),
                "aliases": r["c"].get("aliases", []),
            },
        )
        for r in results
    ]


# Person endpoints
@router.post("/people", response_model=EntityResponse)
async def create_person(person: PersonCreate) -> EntityResponse:
    """Add a new person to the knowledge graph."""
    if not _graph_store:
        raise HTTPException(status_code=503, detail="Graph store not initialized")

    entity = Person(
        name=person.name,
        role=person.role,
        organization=person.organization,
    )

    _graph_store.upsert_person(entity)

    if _vector_store:
        text = f"{person.name}"
        if person.role:
            text += f", {person.role}"
        if person.organization:
            text += f" at {person.organization}"
        _vector_store.add_document(
            entity.id,
            text,
            {"title": person.name, "type": "person"},
        )

    return EntityResponse(
        id=entity.id,
        name=entity.name,
        type="person",
        details={"role": entity.role, "organization": entity.organization},
    )


@router.get("/people", response_model=List[EntityResponse])
async def list_people(
    limit: int = Query(50, ge=1, le=200),
) -> List[EntityResponse]:
    """List all people."""
    if not _graph_store:
        raise HTTPException(status_code=503, detail="Graph store not initialized")

    query = "MATCH (p:Person) RETURN p LIMIT $limit"
    results = _graph_store.execute_cypher(query, {"limit": limit})

    return [
        EntityResponse(
            id=r["p"].get("id", ""),
            name=r["p"].get("name", ""),
            type="person",
            details={
                "role": r["p"].get("role", ""),
                "organization": r["p"].get("organization", ""),
            },
        )
        for r in results
    ]


# Resource endpoints
@router.post("/resources", response_model=EntityResponse)
async def create_resource(resource: ResourceCreate) -> EntityResponse:
    """Add a new resource to the knowledge graph."""
    if not _graph_store:
        raise HTTPException(status_code=503, detail="Graph store not initialized")

    entity = Resource(
        name=resource.name,
        resource_type=resource.resource_type,
        url=resource.url,
        description=resource.description,
    )

    _graph_store.upsert_resource(entity)

    if _vector_store:
        text = f"{resource.name}: {resource.description}"
        _vector_store.add_document(
            entity.id,
            text,
            {"title": resource.name, "type": "resource"},
        )

    return EntityResponse(
        id=entity.id,
        name=entity.name,
        type="resource",
        details={
            "resource_type": entity.resource_type,
            "url": entity.url,
            "description": entity.description,
        },
    )


# Project endpoints
@router.get("/projects", response_model=List[ProjectResponse])
async def list_projects() -> List[ProjectResponse]:
    """List all projects."""
    if not _graph_store:
        raise HTTPException(status_code=503, detail="Graph store not initialized")

    projects = _graph_store.get_all_projects()

    return [
        ProjectResponse(
            id=p.get("id", ""),
            name=p.get("name", ""),
            folder_path=p.get("folder_path", ""),
            description=p.get("description", ""),
            document_count=p.get("document_count", 0),
        )
        for p in projects
    ]


@router.get("/projects/{project_id}/documents")
async def get_project_documents(project_id: str) -> List[dict]:
    """Get all documents in a project."""
    if not _graph_store:
        raise HTTPException(status_code=503, detail="Graph store not initialized")

    documents = _graph_store.get_documents_by_project(project_id)

    return [
        {
            "id": d.get("id", ""),
            "title": d.get("title", ""),
            "file_path": d.get("file_path", ""),
            "file_type": d.get("file_type", ""),
            "summary": d.get("summary", ""),
        }
        for d in documents
    ]


# Statistics
@router.get("/stats")
async def get_stats() -> dict:
    """Get knowledge base statistics."""
    stats = {
        "graph": {},
        "vector": {},
    }

    if _graph_store:
        stats["graph"] = _graph_store.get_graph_stats()

    if _vector_store:
        stats["vector"] = _vector_store.get_stats()

    return stats
