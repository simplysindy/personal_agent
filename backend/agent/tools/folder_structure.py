"""Folder structure tool for querying project and document organization."""

from typing import Optional
from collections import defaultdict
from langchain_core.tools import tool

from backend.knowledge.graph_store import GraphStore


# Global store instance
_graph_store: Optional[GraphStore] = None


def set_graph_store(store: GraphStore) -> None:
    """Set the graph store instance."""
    global _graph_store
    _graph_store = store


@tool
def list_projects_tool() -> str:
    """
    List all projects (top-level folders) in the vault.

    Use this tool when the user asks about:
    - What projects/folders exist
    - Overview of the vault structure
    - Navigating between different areas of knowledge

    Returns:
        List of all projects with their document counts
    """
    if not _graph_store:
        return "Graph store not initialized"

    try:
        projects = _graph_store.get_all_projects()

        if not projects:
            return "No projects found in the vault"

        output_parts = ["Projects in your vault:\n"]
        for project in projects:
            name = project.get("name", "Unknown")
            doc_count = project.get("document_count", 0)
            folder_path = project.get("folder_path", "")
            output_parts.append(f"- {name}/ ({doc_count} documents)")

        return "\n".join(output_parts)

    except Exception as e:
        return f"Error listing projects: {e}"


@tool
def list_project_contents_tool(project_name: str) -> str:
    """
    List all documents and files within a specific project/folder.

    Use this tool when the user asks about:
    - What files are in a specific folder
    - How a folder is organized
    - Contents of a project
    - How to rearrange or organize a folder

    Args:
        project_name: Name of the project/folder to list contents for

    Returns:
        Hierarchical view of all documents in the project
    """
    if not _graph_store:
        return "Graph store not initialized"

    try:
        # Get all documents with file paths containing the project name
        query = """
        MATCH (d:Document)-[:PART_OF]->(p:Project)
        WHERE toLower(p.name) CONTAINS toLower($project_name)
           OR toLower(p.folder_path) CONTAINS toLower($project_name)
        RETURN d.title as title, d.file_path as file_path,
               d.file_type as file_type, d.summary as summary,
               p.name as project_name
        ORDER BY d.file_path
        """
        results = _graph_store.execute_cypher(query, {"project_name": project_name})

        if not results:
            # Try direct search in file paths
            query2 = """
            MATCH (d:Document)
            WHERE toLower(d.file_path) STARTS WITH toLower($project_name)
            RETURN d.title as title, d.file_path as file_path,
                   d.file_type as file_type, d.summary as summary
            ORDER BY d.file_path
            """
            results = _graph_store.execute_cypher(query2, {"project_name": project_name})

        if not results:
            return f"No documents found in project/folder: {project_name}"

        # Group by subfolder
        folder_structure = defaultdict(list)
        for doc in results:
            file_path = doc.get("file_path", "")
            title = doc.get("title", "Unknown")
            file_type = doc.get("file_type", "unknown")
            summary = doc.get("summary", "")[:100] if doc.get("summary") else ""

            # Extract subfolder from path
            parts = file_path.split("/")
            if len(parts) > 2:
                subfolder = "/".join(parts[1:-1])  # Middle parts are subfolders
            else:
                subfolder = "(root)"

            folder_structure[subfolder].append({
                "title": title,
                "file": parts[-1] if parts else file_path,
                "type": file_type,
                "summary": summary,
            })

        # Format output
        output_parts = [f"Contents of '{project_name}':\n"]

        for folder, docs in sorted(folder_structure.items()):
            if folder != "(root)":
                output_parts.append(f"\n{folder}/")
            for doc in docs:
                prefix = "  " if folder != "(root)" else ""
                type_icon = {
                    "markdown": "[MD]",
                    "pdf": "[PDF]",
                    "docx": "[DOC]",
                    "pptx": "[PPT]",
                    "image": "[IMG]",
                }.get(doc["type"], "[?]")
                output_parts.append(f"{prefix}- {type_icon} {doc['title']}")
                if doc["summary"]:
                    output_parts.append(f"{prefix}    {doc['summary']}...")

        output_parts.append(f"\nTotal: {len(results)} documents")
        return "\n".join(output_parts)

    except Exception as e:
        return f"Error listing project contents: {e}"


@tool
def get_folder_summary_tool(project_name: str) -> str:
    """
    Get a summary of a project/folder including document types and key concepts.

    Use this tool to understand what a folder contains at a high level,
    including the types of documents and main topics covered.

    Args:
        project_name: Name of the project/folder to summarize

    Returns:
        Summary of the folder contents and themes
    """
    if not _graph_store:
        return "Graph store not initialized"

    try:
        # Get documents and their concepts
        query = """
        MATCH (d:Document)-[:PART_OF]->(p:Project)
        WHERE toLower(p.name) CONTAINS toLower($project_name)
        OPTIONAL MATCH (d)-[:MENTIONS]->(c:Concept)
        WITH d, collect(DISTINCT c.name) as concepts
        RETURN d.title as title, d.file_path as file_path,
               d.file_type as file_type, d.summary as summary,
               concepts
        ORDER BY d.file_path
        """
        results = _graph_store.execute_cypher(query, {"project_name": project_name})

        if not results:
            return f"No documents found in project: {project_name}"

        # Aggregate stats
        file_types = defaultdict(int)
        all_concepts = defaultdict(int)
        summaries = []

        for doc in results:
            file_type = doc.get("file_type", "unknown")
            file_types[file_type] += 1

            for concept in doc.get("concepts", []):
                if concept:
                    all_concepts[concept] += 1

            if doc.get("summary"):
                summaries.append(f"- {doc['title']}: {doc['summary'][:150]}")

        # Format output
        output_parts = [f"Summary of '{project_name}':\n"]

        output_parts.append("Document types:")
        for ftype, count in sorted(file_types.items(), key=lambda x: -x[1]):
            output_parts.append(f"  - {ftype}: {count} files")

        output_parts.append(f"\nTotal documents: {len(results)}")

        if all_concepts:
            top_concepts = sorted(all_concepts.items(), key=lambda x: -x[1])[:10]
            output_parts.append("\nKey concepts/topics:")
            for concept, count in top_concepts:
                output_parts.append(f"  - {concept} (mentioned {count}x)")

        if summaries[:5]:
            output_parts.append("\nDocument summaries:")
            output_parts.extend(summaries[:5])

        return "\n".join(output_parts)

    except Exception as e:
        return f"Error summarizing folder: {e}"
