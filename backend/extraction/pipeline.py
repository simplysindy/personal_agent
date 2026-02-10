"""Main extraction pipeline orchestrator."""

import hashlib
from pathlib import Path
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from backend.config import settings
from backend.knowledge.models import (
    Document,
    Project,
    Concept,
    Person,
    Resource,
    Image,
    ExtractedContent,
    FileType,
)
from backend.knowledge.graph_store import GraphStore
from backend.knowledge.vector_store import VectorStore

from .parsers import (
    MarkdownParser,
    PDFParser,
    DocxParser,
    PptxParser,
    ImageParser,
)
from .extractors import NLPExtractor, LLMExtractor


class ExtractionPipeline:
    """Orchestrates extraction from vault files to knowledge graph."""

    # File extension to parser mapping
    PARSERS = {
        ".md": ("markdown", MarkdownParser),
        ".pdf": ("pdf", PDFParser),
        ".docx": ("docx", DocxParser),
        ".pptx": ("pptx", PptxParser),
        ".png": ("image", ImageParser),
        ".jpg": ("image", ImageParser),
        ".jpeg": ("image", ImageParser),
        ".gif": ("image", ImageParser),
    }

    # File type mapping
    FILE_TYPES = {
        ".md": FileType.MARKDOWN,
        ".pdf": FileType.PDF,
        ".docx": FileType.DOCX,
        ".pptx": FileType.PPTX,
        ".png": FileType.IMAGE,
        ".jpg": FileType.IMAGE,
        ".jpeg": FileType.IMAGE,
        ".gif": FileType.IMAGE,
    }

    def __init__(
        self,
        vault_path: Path = None,
        graph_store: GraphStore = None,
        vector_store: VectorStore = None,
        use_llm: bool = True,
        use_vision: bool = True,
    ):
        self.vault_path = vault_path or settings.vault_path
        self.graph_store = graph_store or GraphStore()
        self.vector_store = vector_store or VectorStore()

        # Initialize parsers
        self.md_parser = MarkdownParser()
        self.pdf_parser = PDFParser(extract_images=use_vision)
        self.docx_parser = DocxParser()
        self.pptx_parser = PptxParser()
        self.image_parser = ImageParser(use_ocr=True, use_vision_llm=use_vision)

        # Initialize extractors
        self.nlp_extractor = NLPExtractor()
        self.llm_extractor = LLMExtractor() if use_llm else None

        self._use_llm = use_llm
        self._use_vision = use_vision

    def initialize(self) -> None:
        """Initialize database connections and schema."""
        self.graph_store.connect()
        self.graph_store.initialize_schema()
        self.vector_store.connect()

    def close(self) -> None:
        """Close database connections."""
        self.graph_store.close()

    def scan_vault(self) -> dict:
        """Scan the vault and return file statistics."""
        stats = {ext: 0 for ext in self.PARSERS.keys()}
        stats["projects"] = 0
        stats["total_files"] = 0

        vault = Path(self.vault_path)

        # Count projects (top-level folders)
        for item in vault.iterdir():
            if item.is_dir() and not item.name.startswith("."):
                stats["projects"] += 1

        # Count files by type
        for ext in self.PARSERS.keys():
            files = list(vault.rglob(f"*{ext}"))
            stats[ext] = len(files)
            stats["total_files"] += len(files)

        return stats

    def extract_projects(self) -> list[Project]:
        """Extract project information from vault folder structure."""
        projects = []
        vault = Path(self.vault_path)

        for folder in vault.iterdir():
            if folder.is_dir() and not folder.name.startswith("."):
                # Count documents in project
                doc_count = 0
                for ext in self.PARSERS.keys():
                    doc_count += len(list(folder.rglob(f"*{ext}")))

                project = Project(
                    name=folder.name,
                    folder_path=str(folder.relative_to(vault)),
                    document_count=doc_count,
                )
                projects.append(project)

        return projects

    def extract_file(self, file_path: Path) -> Optional[ExtractedContent]:
        """Extract content from a single file."""
        ext = file_path.suffix.lower()

        if ext not in self.PARSERS:
            return None

        file_type = self.FILE_TYPES.get(ext, FileType.MARKDOWN)

        try:
            if ext == ".md":
                return self._extract_markdown(file_path, file_type)
            elif ext == ".pdf":
                return self._extract_pdf(file_path, file_type)
            elif ext == ".docx":
                return self._extract_docx(file_path, file_type)
            elif ext == ".pptx":
                return self._extract_pptx(file_path, file_type)
            elif ext in (".png", ".jpg", ".jpeg", ".gif"):
                return self._extract_image(file_path, file_type)
        except Exception as e:
            print(f"Error extracting {file_path}: {e}")
            return None

        return None

    def _extract_markdown(
        self, file_path: Path, file_type: FileType
    ) -> ExtractedContent:
        """Extract content from markdown file."""
        parsed = self.md_parser.parse_file(file_path)

        # Create document
        doc = Document(
            title=parsed.title,
            file_path=str(file_path.relative_to(self.vault_path)),
            file_type=file_type,
            extracted_text=parsed.text,
            content_hash=hashlib.md5(parsed.text.encode()).hexdigest(),
            frontmatter=parsed.frontmatter,
            tags=parsed.tags,
            links=parsed.links,
        )

        # Extract entities via NLP
        nlp_entities = self.nlp_extractor.extract(parsed.text)

        # Extract via LLM if enabled
        llm_content = None
        if self._use_llm and self.llm_extractor:
            llm_content = self.llm_extractor.extract(parsed.text, parsed.title)
            doc.summary = llm_content.summary

        # Build extracted content
        content = ExtractedContent(document=doc)

        # Convert NLP entities to models
        for person in nlp_entities.people:
            content.people.append(Person(name=person["text"]))

        # Add concepts from LLM
        if llm_content:
            for concept in llm_content.concepts:
                content.concepts.append(
                    Concept(
                        name=concept.get("name", ""),
                        definition=concept.get("definition", ""),
                    )
                )

        # Add technologies as concepts
        for tech in nlp_entities.technologies:
            content.concepts.append(
                Concept(name=tech["text"], definition=f"Technology: {tech['text']}")
            )

        # Linked documents from wiki links
        content.linked_documents = parsed.wiki_links

        # Images referenced in markdown
        for img_path in parsed.images:
            content.images.append(
                Image(file_path=img_path, source_document_id=doc.id)
            )

        # Create chunks for vector store
        content.chunks = self._create_chunks(parsed.text)

        return content

    def _extract_pdf(self, file_path: Path, file_type: FileType) -> ExtractedContent:
        """Extract content from PDF file."""
        parsed = self.pdf_parser.parse_file(file_path)

        doc = Document(
            title=parsed.title,
            file_path=str(file_path.relative_to(self.vault_path)),
            file_type=file_type,
            extracted_text=parsed.text,
            content_hash=hashlib.md5(parsed.text.encode()).hexdigest(),
            page_count=parsed.page_count,
        )

        # NLP extraction
        nlp_entities = self.nlp_extractor.extract(parsed.text)

        # LLM extraction
        if self._use_llm and self.llm_extractor:
            llm_content = self.llm_extractor.extract(parsed.text, parsed.title)
            doc.summary = llm_content.summary

        content = ExtractedContent(document=doc)

        for person in nlp_entities.people:
            content.people.append(Person(name=person["text"]))

        for tech in nlp_entities.technologies:
            content.concepts.append(
                Concept(name=tech["text"], definition=f"Technology: {tech['text']}")
            )

        # Process embedded images if vision enabled
        if self._use_vision and parsed.images:
            for i, img in enumerate(parsed.images[:5]):  # Limit to 5 images
                img_parsed = self.image_parser.parse_bytes(
                    img.image_bytes,
                    img.image_format,
                    f"{file_path.stem}_page{img.page_number}_img{i}",
                )
                content.images.append(
                    Image(
                        file_path=f"{file_path.stem}_embedded_{i}",
                        description=img_parsed.vision_description,
                        ocr_text=img_parsed.ocr_text,
                        source_document_id=doc.id,
                    )
                )

        content.chunks = self._create_chunks(parsed.text)

        return content

    def _extract_docx(self, file_path: Path, file_type: FileType) -> ExtractedContent:
        """Extract content from Word document."""
        parsed = self.docx_parser.parse_file(file_path)

        doc = Document(
            title=parsed.title,
            file_path=str(file_path.relative_to(self.vault_path)),
            file_type=file_type,
            extracted_text=parsed.text,
            content_hash=hashlib.md5(parsed.text.encode()).hexdigest(),
        )

        nlp_entities = self.nlp_extractor.extract(parsed.text)

        if self._use_llm and self.llm_extractor:
            llm_content = self.llm_extractor.extract(parsed.text, parsed.title)
            doc.summary = llm_content.summary

        content = ExtractedContent(document=doc)

        for person in nlp_entities.people:
            content.people.append(Person(name=person["text"]))

        for tech in nlp_entities.technologies:
            content.concepts.append(
                Concept(name=tech["text"], definition=f"Technology: {tech['text']}")
            )

        content.chunks = self._create_chunks(parsed.text)

        return content

    def _extract_pptx(self, file_path: Path, file_type: FileType) -> ExtractedContent:
        """Extract content from PowerPoint presentation."""
        parsed = self.pptx_parser.parse_file(file_path)

        doc = Document(
            title=parsed.title,
            file_path=str(file_path.relative_to(self.vault_path)),
            file_type=file_type,
            extracted_text=parsed.text,
            content_hash=hashlib.md5(parsed.text.encode()).hexdigest(),
            page_count=parsed.slide_count,
        )

        nlp_entities = self.nlp_extractor.extract(parsed.text)

        if self._use_llm and self.llm_extractor:
            llm_content = self.llm_extractor.extract(parsed.text, parsed.title)
            doc.summary = llm_content.summary

        content = ExtractedContent(document=doc)

        for person in nlp_entities.people:
            content.people.append(Person(name=person["text"]))

        for tech in nlp_entities.technologies:
            content.concepts.append(
                Concept(name=tech["text"], definition=f"Technology: {tech['text']}")
            )

        content.chunks = self._create_chunks(parsed.text)

        return content

    def _extract_image(self, file_path: Path, file_type: FileType) -> ExtractedContent:
        """Extract content from image file."""
        parsed = self.image_parser.parse_file(file_path)

        text = ""
        if parsed.ocr_text:
            text += f"OCR Text: {parsed.ocr_text}\n\n"
        if parsed.vision_description:
            text += f"Description: {parsed.vision_description}"

        doc = Document(
            title=file_path.stem,
            file_path=str(file_path.relative_to(self.vault_path)),
            file_type=file_type,
            extracted_text=text,
            ocr_text=parsed.ocr_text,
            vision_description=parsed.vision_description,
            content_hash=hashlib.md5(text.encode()).hexdigest() if text else "",
        )

        content = ExtractedContent(document=doc)

        # Extract entities from OCR text if available
        if parsed.ocr_text:
            nlp_entities = self.nlp_extractor.extract(parsed.ocr_text)
            for tech in nlp_entities.technologies:
                content.concepts.append(
                    Concept(name=tech["text"], definition=f"Technology: {tech['text']}")
                )

        content.images.append(
            Image(
                file_path=str(file_path.relative_to(self.vault_path)),
                description=parsed.vision_description,
                ocr_text=parsed.ocr_text,
            )
        )

        if text:
            content.chunks = [text]

        return content

    def _create_chunks(
        self, text: str, chunk_size: int = 1000, overlap: int = 200
    ) -> list[str]:
        """Split text into overlapping chunks for vector storage."""
        if not text:
            return []

        chunks = []
        start = 0

        while start < len(text):
            end = start + chunk_size

            # Try to end at a sentence boundary
            if end < len(text):
                # Look for sentence end
                for sep in [". ", ".\n", "\n\n", "\n"]:
                    last_sep = text[start:end].rfind(sep)
                    if last_sep > chunk_size // 2:
                        end = start + last_sep + len(sep)
                        break

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            start = end - overlap

        return chunks

    def store_extracted_content(self, content: ExtractedContent) -> None:
        """Store extracted content in graph and vector databases."""
        doc = content.document

        # Store document in graph
        self.graph_store.upsert_document(doc)

        # Store in vector store
        if doc.extracted_text:
            self.vector_store.add_document(
                doc.id,
                doc.extracted_text[:10000],  # Limit for embedding
                {
                    "title": doc.title,
                    "file_path": doc.file_path,
                    "file_type": doc.file_type.value,
                    "summary": doc.summary[:500] if doc.summary else "",
                },
            )

        # Store chunks
        if content.chunks:
            self.vector_store.add_chunks(
                doc.id,
                content.chunks,
                {
                    "title": doc.title,
                    "file_path": doc.file_path,
                    "file_type": doc.file_type.value,
                },
            )

        # Store concepts
        for concept in content.concepts:
            if concept.name:
                self.graph_store.upsert_concept(concept)
                self.graph_store.link_document_mentions(doc.id, "Concept", concept.id)

        # Store people
        for person in content.people:
            if person.name:
                self.graph_store.upsert_person(person)
                self.graph_store.link_document_mentions(doc.id, "Person", person.id)

        # Store images
        for image in content.images:
            if image.file_path:
                image.source_document_id = doc.id
                self.graph_store.upsert_image(image)
                self.graph_store.create_relationship(
                    "Document", doc.id, "Image", image.id, "CONTAINS_IMAGE"
                )

    def link_document_to_project(self, doc_id: str, file_path: str) -> None:
        """Link a document to its project based on file path."""
        path = Path(file_path)
        parts = path.parts

        if parts:
            # First part after vault root is the project folder
            project_folder = parts[0]
            project = Project(
                name=project_folder,
                folder_path=project_folder,
            )
            self.graph_store.upsert_project(project)
            self.graph_store.link_document_to_project(doc_id, project.id)

    def process_vault(
        self,
        parallel: bool = True,
        max_workers: int = 4,
        progress_callback=None,
    ) -> dict:
        """Process entire vault and build knowledge graph."""
        self.initialize()

        stats = {
            "processed": 0,
            "failed": 0,
            "projects": 0,
            "documents": 0,
            "concepts": 0,
            "people": 0,
        }

        vault = Path(self.vault_path)

        # Extract and store projects
        projects = self.extract_projects()
        for project in projects:
            self.graph_store.upsert_project(project)
            stats["projects"] += 1

        # Collect all files to process
        files_to_process = []
        for ext in self.PARSERS.keys():
            files_to_process.extend(vault.rglob(f"*{ext}"))

        total_files = len(files_to_process)

        if parallel and max_workers > 1:
            # Parallel processing
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {
                    executor.submit(self.extract_file, f): f
                    for f in files_to_process
                }

                for i, future in enumerate(as_completed(futures)):
                    file_path = futures[future]
                    try:
                        content = future.result()
                        if content:
                            self.store_extracted_content(content)
                            self.link_document_to_project(
                                content.document.id,
                                content.document.file_path,
                            )
                            stats["documents"] += 1
                            stats["concepts"] += len(content.concepts)
                            stats["people"] += len(content.people)
                        stats["processed"] += 1
                    except Exception as e:
                        print(f"Failed to process {file_path}: {e}")
                        stats["failed"] += 1

                    if progress_callback:
                        progress_callback(i + 1, total_files, str(file_path))
        else:
            # Sequential processing
            for i, file_path in enumerate(files_to_process):
                try:
                    content = self.extract_file(file_path)
                    if content:
                        self.store_extracted_content(content)
                        self.link_document_to_project(
                            content.document.id,
                            content.document.file_path,
                        )
                        stats["documents"] += 1
                        stats["concepts"] += len(content.concepts)
                        stats["people"] += len(content.people)
                    stats["processed"] += 1
                except Exception as e:
                    print(f"Failed to process {file_path}: {e}")
                    stats["failed"] += 1

                if progress_callback:
                    progress_callback(i + 1, total_files, str(file_path))

        # Link documents based on wiki links
        self._link_documents()

        return stats

    def _link_documents(self) -> None:
        """Create LINKS_TO relationships between documents based on wiki links."""
        # This would query all documents and their links, then create relationships
        # For now, this is a placeholder - actual implementation would query Neo4j
        pass

    def process_single_file(self, file_path: Path) -> Optional[ExtractedContent]:
        """Process a single file (for incremental updates)."""
        self.initialize()

        content = self.extract_file(file_path)
        if content:
            self.store_extracted_content(content)
            self.link_document_to_project(
                content.document.id,
                content.document.file_path,
            )

        return content
