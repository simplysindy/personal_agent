"""ChromaDB vector store operations."""

from typing import Optional
import chromadb
from chromadb.config import Settings as ChromaSettings

from backend.config import settings


class VectorStore:
    """ChromaDB vector database operations."""

    def __init__(
        self,
        persist_directory: str = None,
        collection_name: str = settings.chroma_collection_name,
    ):
        self._persist_directory = persist_directory or str(settings.chroma_path)
        self._collection_name = collection_name
        self._client: Optional[chromadb.Client] = None
        self._collection = None

    def connect(self) -> None:
        """Initialize ChromaDB client and collection."""
        self._client = chromadb.PersistentClient(
            path=self._persist_directory,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=self._collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    @property
    def collection(self):
        """Get the collection, connecting if necessary."""
        if not self._collection:
            self.connect()
        return self._collection

    def add_document(
        self,
        doc_id: str,
        text: str,
        metadata: dict = None,
    ) -> None:
        """Add a single document to the vector store."""
        self.collection.add(
            ids=[doc_id],
            documents=[text],
            metadatas=[metadata or {}],
        )

    def add_chunks(
        self,
        doc_id: str,
        chunks: list[str],
        metadata: dict = None,
    ) -> None:
        """Add document chunks to the vector store."""
        base_metadata = metadata or {}
        ids = [f"{doc_id}_chunk_{i}" for i in range(len(chunks))]
        metadatas = [{**base_metadata, "chunk_index": i, "parent_doc_id": doc_id} for i in range(len(chunks))]

        self.collection.add(
            ids=ids,
            documents=chunks,
            metadatas=metadatas,
        )

    def add_documents_batch(
        self,
        doc_ids: list[str],
        texts: list[str],
        metadatas: list[dict] = None,
    ) -> None:
        """Add multiple documents in batch."""
        metadatas = metadatas or [{} for _ in doc_ids]
        self.collection.add(
            ids=doc_ids,
            documents=texts,
            metadatas=metadatas,
        )

    def search(
        self,
        query: str,
        n_results: int = 10,
        where: dict = None,
        where_document: dict = None,
    ) -> dict:
        """Search for similar documents."""
        return self.collection.query(
            query_texts=[query],
            n_results=n_results,
            where=where,
            where_document=where_document,
            include=["documents", "metadatas", "distances"],
        )

    def search_by_embedding(
        self,
        embedding: list[float],
        n_results: int = 10,
        where: dict = None,
    ) -> dict:
        """Search using a pre-computed embedding."""
        return self.collection.query(
            query_embeddings=[embedding],
            n_results=n_results,
            where=where,
            include=["documents", "metadatas", "distances"],
        )

    def get_document(self, doc_id: str) -> Optional[dict]:
        """Get a document by ID."""
        result = self.collection.get(
            ids=[doc_id],
            include=["documents", "metadatas"],
        )
        if result["ids"]:
            return {
                "id": result["ids"][0],
                "document": result["documents"][0] if result["documents"] else None,
                "metadata": result["metadatas"][0] if result["metadatas"] else {},
            }
        return None

    def get_documents_by_metadata(
        self,
        where: dict,
        limit: int = 100,
    ) -> dict:
        """Get documents matching metadata filter."""
        return self.collection.get(
            where=where,
            limit=limit,
            include=["documents", "metadatas"],
        )

    def update_document(
        self,
        doc_id: str,
        text: str = None,
        metadata: dict = None,
    ) -> None:
        """Update a document's text and/or metadata."""
        update_args = {"ids": [doc_id]}
        if text:
            update_args["documents"] = [text]
        if metadata:
            update_args["metadatas"] = [metadata]
        self.collection.update(**update_args)

    def delete_document(self, doc_id: str) -> None:
        """Delete a document by ID."""
        self.collection.delete(ids=[doc_id])

    def delete_by_metadata(self, where: dict) -> None:
        """Delete documents matching metadata filter."""
        self.collection.delete(where=where)

    def delete_document_chunks(self, doc_id: str) -> None:
        """Delete all chunks belonging to a document."""
        self.collection.delete(where={"parent_doc_id": doc_id})

    def count(self) -> int:
        """Get total number of documents in the collection."""
        return self.collection.count()

    def clear_all(self) -> None:
        """Delete all documents. Use with caution!"""
        # ChromaDB doesn't have a clear method, so we delete and recreate
        self._client.delete_collection(self._collection_name)
        self._collection = self._client.create_collection(
            name=self._collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def get_stats(self) -> dict:
        """Get statistics about the vector store."""
        return {
            "collection_name": self._collection_name,
            "document_count": self.count(),
        }
