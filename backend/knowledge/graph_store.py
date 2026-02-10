"""Neo4j graph store operations."""

from typing import Any, Optional
from neo4j import GraphDatabase, Driver
from contextlib import contextmanager

from backend.config import settings
from backend.knowledge.models import (
    Document,
    Project,
    Concept,
    Person,
    Resource,
    Image,
    Relationship,
)


class GraphStore:
    """Neo4j graph database operations."""

    def __init__(
        self,
        uri: str = settings.neo4j_uri,
        user: str = settings.neo4j_user,
        password: str = settings.neo4j_password,
    ):
        self._driver: Optional[Driver] = None
        self._uri = uri
        self._user = user
        self._password = password

    def connect(self) -> None:
        """Establish connection to Neo4j."""
        self._driver = GraphDatabase.driver(
            self._uri, auth=(self._user, self._password)
        )

    def close(self) -> None:
        """Close the database connection."""
        if self._driver:
            self._driver.close()

    @contextmanager
    def session(self):
        """Get a database session."""
        if not self._driver:
            self.connect()
        session = self._driver.session()
        try:
            yield session
        finally:
            session.close()

    def initialize_schema(self) -> None:
        """Create indexes and constraints."""
        constraints = [
            "CREATE CONSTRAINT document_id IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE",
            "CREATE CONSTRAINT project_id IF NOT EXISTS FOR (p:Project) REQUIRE p.id IS UNIQUE",
            "CREATE CONSTRAINT concept_id IF NOT EXISTS FOR (c:Concept) REQUIRE c.id IS UNIQUE",
            "CREATE CONSTRAINT person_id IF NOT EXISTS FOR (p:Person) REQUIRE p.id IS UNIQUE",
            "CREATE CONSTRAINT resource_id IF NOT EXISTS FOR (r:Resource) REQUIRE r.id IS UNIQUE",
            "CREATE CONSTRAINT image_id IF NOT EXISTS FOR (i:Image) REQUIRE i.id IS UNIQUE",
        ]
        indexes = [
            "CREATE INDEX document_title IF NOT EXISTS FOR (d:Document) ON (d.title)",
            "CREATE INDEX document_file_type IF NOT EXISTS FOR (d:Document) ON (d.file_type)",
            "CREATE INDEX concept_name IF NOT EXISTS FOR (c:Concept) ON (c.name)",
            "CREATE INDEX person_name IF NOT EXISTS FOR (p:Person) ON (p.name)",
            "CREATE INDEX project_name IF NOT EXISTS FOR (p:Project) ON (p.name)",
        ]
        with self.session() as session:
            for constraint in constraints:
                session.run(constraint)
            for index in indexes:
                session.run(index)

    # Document operations
    def upsert_document(self, doc: Document) -> None:
        """Create or update a document node."""
        query = """
        MERGE (d:Document {id: $id})
        SET d.title = $title,
            d.file_path = $file_path,
            d.file_type = $file_type,
            d.content_hash = $content_hash,
            d.summary = $summary,
            d.extracted_text = $extracted_text,
            d.page_count = $page_count,
            d.tags = $tags,
            d.updated_at = datetime()
        """
        with self.session() as session:
            session.run(
                query,
                id=doc.id,
                title=doc.title,
                file_path=doc.file_path,
                file_type=doc.file_type.value,
                content_hash=doc.content_hash,
                summary=doc.summary,
                extracted_text=doc.extracted_text[:5000],  # Limit text stored in graph
                page_count=doc.page_count,
                tags=doc.tags,
            )

    def get_document(self, doc_id: str) -> Optional[dict]:
        """Get a document by ID."""
        query = "MATCH (d:Document {id: $id}) RETURN d"
        with self.session() as session:
            result = session.run(query, id=doc_id)
            record = result.single()
            return dict(record["d"]) if record else None

    def get_documents_by_project(self, project_id: str) -> list[dict]:
        """Get all documents in a project."""
        query = """
        MATCH (d:Document)-[:PART_OF]->(p:Project {id: $project_id})
        RETURN d
        """
        with self.session() as session:
            result = session.run(query, project_id=project_id)
            return [dict(record["d"]) for record in result]

    # Project operations
    def upsert_project(self, project: Project) -> None:
        """Create or update a project node."""
        query = """
        MERGE (p:Project {id: $id})
        SET p.name = $name,
            p.folder_path = $folder_path,
            p.description = $description,
            p.document_count = $document_count,
            p.updated_at = datetime()
        """
        with self.session() as session:
            session.run(
                query,
                id=project.id,
                name=project.name,
                folder_path=project.folder_path,
                description=project.description,
                document_count=project.document_count,
            )

    def get_all_projects(self) -> list[dict]:
        """Get all projects."""
        query = "MATCH (p:Project) RETURN p ORDER BY p.name"
        with self.session() as session:
            result = session.run(query)
            return [dict(record["p"]) for record in result]

    # Concept operations
    def upsert_concept(self, concept: Concept) -> None:
        """Create or update a concept node."""
        query = """
        MERGE (c:Concept {id: $id})
        SET c.name = $name,
            c.definition = $definition,
            c.aliases = $aliases,
            c.updated_at = datetime()
        """
        with self.session() as session:
            session.run(
                query,
                id=concept.id,
                name=concept.name,
                definition=concept.definition,
                aliases=concept.aliases,
            )

    def get_concepts_by_document(self, doc_id: str) -> list[dict]:
        """Get all concepts mentioned in a document."""
        query = """
        MATCH (d:Document {id: $doc_id})-[:MENTIONS]->(c:Concept)
        RETURN c
        """
        with self.session() as session:
            result = session.run(query, doc_id=doc_id)
            return [dict(record["c"]) for record in result]

    # Person operations
    def upsert_person(self, person: Person) -> None:
        """Create or update a person node."""
        query = """
        MERGE (p:Person {id: $id})
        SET p.name = $name,
            p.role = $role,
            p.organization = $organization,
            p.updated_at = datetime()
        """
        with self.session() as session:
            session.run(
                query,
                id=person.id,
                name=person.name,
                role=person.role,
                organization=person.organization,
            )

    # Resource operations
    def upsert_resource(self, resource: Resource) -> None:
        """Create or update a resource node."""
        query = """
        MERGE (r:Resource {id: $id})
        SET r.name = $name,
            r.resource_type = $resource_type,
            r.url = $url,
            r.description = $description,
            r.updated_at = datetime()
        """
        with self.session() as session:
            session.run(
                query,
                id=resource.id,
                name=resource.name,
                resource_type=resource.resource_type,
                url=resource.url,
                description=resource.description,
            )

    # Image operations
    def upsert_image(self, image: Image) -> None:
        """Create or update an image node."""
        query = """
        MERGE (i:Image {id: $id})
        SET i.file_path = $file_path,
            i.description = $description,
            i.ocr_text = $ocr_text,
            i.source_document_id = $source_document_id,
            i.updated_at = datetime()
        """
        with self.session() as session:
            session.run(
                query,
                id=image.id,
                file_path=image.file_path,
                description=image.description,
                ocr_text=image.ocr_text,
                source_document_id=image.source_document_id,
            )

    # Relationship operations
    def create_relationship(
        self,
        source_label: str,
        source_id: str,
        target_label: str,
        target_id: str,
        rel_type: str,
        properties: dict = None,
    ) -> None:
        """Create a relationship between two nodes."""
        props = properties or {}
        props_str = ", ".join(f"r.{k} = ${k}" for k in props.keys())
        set_clause = f"SET {props_str}" if props_str else ""

        query = f"""
        MATCH (a:{source_label} {{id: $source_id}})
        MATCH (b:{target_label} {{id: $target_id}})
        MERGE (a)-[r:{rel_type}]->(b)
        {set_clause}
        """
        with self.session() as session:
            session.run(query, source_id=source_id, target_id=target_id, **props)

    def link_document_to_project(self, doc_id: str, project_id: str) -> None:
        """Link a document to a project."""
        self.create_relationship("Document", doc_id, "Project", project_id, "PART_OF")

    def link_document_mentions(
        self, doc_id: str, entity_label: str, entity_id: str
    ) -> None:
        """Create a MENTIONS relationship from document to entity."""
        self.create_relationship("Document", doc_id, entity_label, entity_id, "MENTIONS")

    def link_documents(self, source_doc_id: str, target_doc_id: str) -> None:
        """Create a LINKS_TO relationship between documents."""
        self.create_relationship(
            "Document", source_doc_id, "Document", target_doc_id, "LINKS_TO"
        )

    def link_concepts(self, concept1_id: str, concept2_id: str) -> None:
        """Create a RELATES_TO relationship between concepts."""
        self.create_relationship(
            "Concept", concept1_id, "Concept", concept2_id, "RELATES_TO"
        )

    # Query operations
    def execute_cypher(self, cypher_query: str, params: dict = None) -> list[dict]:
        """Execute a raw Cypher query."""
        with self.session() as session:
            result = session.run(cypher_query, params or {})
            return [dict(record) for record in result]

    def find_paths(
        self,
        start_id: str,
        end_id: str,
        max_hops: int = 3,
    ) -> list[list[dict]]:
        """Find paths between two nodes."""
        query = f"""
        MATCH path = shortestPath(
            (start {{id: $start_id}})-[*1..{max_hops}]-(end {{id: $end_id}})
        )
        RETURN path
        """
        with self.session() as session:
            result = session.run(query, start_id=start_id, end_id=end_id)
            paths = []
            for record in result:
                path = record["path"]
                path_nodes = [dict(node) for node in path.nodes]
                paths.append(path_nodes)
            return paths

    def get_neighbors(self, node_id: str, depth: int = 1) -> dict:
        """Get neighboring nodes up to specified depth."""
        query = f"""
        MATCH (n {{id: $node_id}})-[r*1..{depth}]-(neighbor)
        RETURN DISTINCT neighbor, type(r[0]) as relationship
        """
        with self.session() as session:
            result = session.run(query, node_id=node_id)
            neighbors = []
            for record in result:
                neighbors.append({
                    "node": dict(record["neighbor"]),
                    "relationship": record["relationship"],
                })
            return neighbors

    def search_nodes(self, query_text: str, labels: list[str] = None) -> list[dict]:
        """Full-text search across nodes."""
        labels = labels or ["Document", "Concept", "Person", "Resource"]
        results = []

        for label in labels:
            search_query = f"""
            MATCH (n:{label})
            WHERE toLower(n.name) CONTAINS toLower($search_text)
               OR toLower(n.title) CONTAINS toLower($search_text)
               OR toLower(n.description) CONTAINS toLower($search_text)
               OR toLower(n.extracted_text) CONTAINS toLower($search_text)
            RETURN n, '{label}' as label
            LIMIT 10
            """
            with self.session() as session:
                result = session.run(search_query, search_text=query_text)
                for record in result:
                    results.append({
                        "node": dict(record["n"]),
                        "label": record["label"],
                    })

        return results

    def get_graph_stats(self) -> dict:
        """Get statistics about the graph."""
        query = """
        CALL {
            MATCH (d:Document) RETURN 'Document' as label, count(d) as count
            UNION ALL
            MATCH (p:Project) RETURN 'Project' as label, count(p) as count
            UNION ALL
            MATCH (c:Concept) RETURN 'Concept' as label, count(c) as count
            UNION ALL
            MATCH (p:Person) RETURN 'Person' as label, count(p) as count
            UNION ALL
            MATCH (r:Resource) RETURN 'Resource' as label, count(r) as count
            UNION ALL
            MATCH (i:Image) RETURN 'Image' as label, count(i) as count
        }
        RETURN label, count
        """
        with self.session() as session:
            result = session.run(query)
            stats = {record["label"]: record["count"] for record in result}
            return stats

    def get_graph_visualization_data(self, limit: int = 100) -> dict:
        """Get nodes and edges for visualization."""
        query = """
        MATCH (n)
        WITH n LIMIT $limit
        OPTIONAL MATCH (n)-[r]-(m)
        WHERE id(m) < id(n)
        RETURN
            collect(DISTINCT {
                id: n.id,
                label: labels(n)[0],
                name: coalesce(n.name, n.title, 'Unknown')
            }) as nodes,
            collect(DISTINCT {
                source: startNode(r).id,
                target: endNode(r).id,
                type: type(r)
            }) as edges
        """
        with self.session() as session:
            result = session.run(query, limit=limit)
            record = result.single()
            if record:
                return {
                    "nodes": record["nodes"],
                    "edges": [e for e in record["edges"] if e["source"] and e["target"]],
                }
            return {"nodes": [], "edges": []}

    def clear_all(self) -> None:
        """Delete all nodes and relationships. Use with caution!"""
        with self.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
