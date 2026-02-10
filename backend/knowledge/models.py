"""Entity models for the knowledge graph."""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
import hashlib


class FileType(str, Enum):
    """Supported file types."""

    MARKDOWN = "md"
    PDF = "pdf"
    DOCX = "docx"
    PPTX = "pptx"
    IMAGE = "image"


class BaseEntity(BaseModel):
    """Base entity with common fields."""

    id: str = Field(default="")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    def generate_id(self, *args: str) -> str:
        """Generate a deterministic ID from input strings."""
        content = "|".join(str(a) for a in args)
        return hashlib.md5(content.encode()).hexdigest()[:16]


class Document(BaseEntity):
    """A document/note from the vault."""

    title: str
    file_path: str
    file_type: FileType = FileType.MARKDOWN
    content_hash: str = ""
    summary: str = ""
    extracted_text: str = ""
    page_count: int = 1
    ocr_text: str = ""
    vision_description: str = ""
    frontmatter: dict = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)

    def __init__(self, **data):
        super().__init__(**data)
        if not self.id:
            self.id = self.generate_id(self.file_path)
        if not self.content_hash and self.extracted_text:
            self.content_hash = hashlib.md5(self.extracted_text.encode()).hexdigest()


class Project(BaseEntity):
    """A project/folder in the vault."""

    name: str
    folder_path: str
    description: str = ""
    document_count: int = 0

    def __init__(self, **data):
        super().__init__(**data)
        if not self.id:
            self.id = self.generate_id(self.folder_path)


class Concept(BaseEntity):
    """An extracted concept/topic."""

    name: str
    definition: str = ""
    aliases: list[str] = Field(default_factory=list)
    source_documents: list[str] = Field(default_factory=list)

    def __init__(self, **data):
        super().__init__(**data)
        if not self.id:
            self.id = self.generate_id(self.name.lower())


class Person(BaseEntity):
    """A person mentioned in documents."""

    name: str
    role: str = ""
    organization: str = ""
    source_documents: list[str] = Field(default_factory=list)

    def __init__(self, **data):
        super().__init__(**data)
        if not self.id:
            self.id = self.generate_id(self.name.lower())


class Resource(BaseEntity):
    """An external resource (URL, tool, etc.)."""

    name: str
    resource_type: str = ""  # url, tool, book, etc.
    url: str = ""
    description: str = ""
    source_documents: list[str] = Field(default_factory=list)

    def __init__(self, **data):
        super().__init__(**data)
        if not self.id:
            self.id = self.generate_id(self.name.lower(), self.resource_type)


class Image(BaseEntity):
    """An image file or embedded image."""

    file_path: str
    description: str = ""
    ocr_text: str = ""
    source_document_id: str = ""
    depicts: list[str] = Field(default_factory=list)

    def __init__(self, **data):
        super().__init__(**data)
        if not self.id:
            self.id = self.generate_id(self.file_path)


class ExtractedContent(BaseModel):
    """Result of content extraction from a file."""

    document: Document
    concepts: list[Concept] = Field(default_factory=list)
    people: list[Person] = Field(default_factory=list)
    resources: list[Resource] = Field(default_factory=list)
    images: list[Image] = Field(default_factory=list)
    chunks: list[str] = Field(default_factory=list)
    linked_documents: list[str] = Field(default_factory=list)


class Relationship(BaseModel):
    """A relationship between entities."""

    source_id: str
    target_id: str
    relationship_type: str
    properties: dict = Field(default_factory=dict)
