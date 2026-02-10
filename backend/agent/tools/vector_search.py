"""Vector search tool for semantic similarity search."""

from typing import Optional
from langchain_core.tools import tool

from backend.knowledge.vector_store import VectorStore


# Global store instance
_vector_store: Optional[VectorStore] = None


def set_vector_store(store: VectorStore) -> None:
    """Set the vector store instance."""
    global _vector_store
    _vector_store = store


@tool
def vector_search_tool(query: str, num_results: int = 5) -> str:
    """
    Search the knowledge base using semantic similarity.

    Use this tool to find documents and content related to a topic,
    even if the exact words don't match.

    Args:
        query: What to search for (natural language)
        num_results: Number of results to return (default 5, max 10)

    Returns:
        Relevant content from the knowledge base
    """
    if not _vector_store:
        return "Vector store not initialized"

    try:
        num_results = min(max(num_results, 1), 10)

        results = _vector_store.search(query, n_results=num_results)

        if not results or not results.get("documents") or not results["documents"][0]:
            return f"No results found for: {query}"

        # Format results
        output_parts = []
        documents = results["documents"][0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for i, doc in enumerate(documents):
            metadata = metadatas[i] if i < len(metadatas) else {}
            distance = distances[i] if i < len(distances) else 1.0
            similarity = 1.0 - distance

            parts = []
            if metadata.get("title"):
                parts.append(f"**{metadata['title']}**")
            if metadata.get("file_path"):
                parts.append(f"_Source: {metadata['file_path']}_")

            # Truncate content
            content = doc[:500] + "..." if len(doc) > 500 else doc
            parts.append(content)
            parts.append(f"(Relevance: {similarity:.2f})")

            output_parts.append("\n".join(parts))

        return "\n\n---\n\n".join(output_parts)

    except Exception as e:
        return f"Error searching: {e}"


@tool
def search_by_file_type(query: str, file_type: str, num_results: int = 5) -> str:
    """
    Search for content filtered by file type.

    Use this to find specific types of documents like PDFs, presentations, etc.

    Args:
        query: What to search for
        file_type: Type of file (md, pdf, docx, pptx, image)
        num_results: Number of results

    Returns:
        Matching content from the specified file type
    """
    if not _vector_store:
        return "Vector store not initialized"

    try:
        valid_types = {"md", "pdf", "docx", "pptx", "image"}
        if file_type not in valid_types:
            return f"Invalid file type. Must be one of: {', '.join(valid_types)}"

        results = _vector_store.search(
            query,
            n_results=num_results,
            where={"file_type": file_type},
        )

        if not results or not results.get("documents") or not results["documents"][0]:
            return f"No {file_type} files found matching: {query}"

        # Format results
        output_parts = []
        for i, doc in enumerate(results["documents"][0]):
            metadata = results["metadatas"][0][i] if results.get("metadatas") else {}

            parts = []
            if metadata.get("title"):
                parts.append(f"**{metadata['title']}** ({file_type})")
            if metadata.get("file_path"):
                parts.append(f"_Source: {metadata['file_path']}_")

            content = doc[:400] + "..." if len(doc) > 400 else doc
            parts.append(content)

            output_parts.append("\n".join(parts))

        return "\n\n---\n\n".join(output_parts)

    except Exception as e:
        return f"Error searching: {e}"
