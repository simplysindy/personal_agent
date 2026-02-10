"""PDF file parser using PyMuPDF (fitz)."""

from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
import io

import fitz  # PyMuPDF


@dataclass
class ExtractedImage:
    """An image extracted from a PDF."""

    page_number: int
    image_bytes: bytes
    image_format: str
    width: int
    height: int


@dataclass
class ParsedPDF:
    """Result of parsing a PDF file."""

    title: str
    text: str
    page_count: int
    pages: list[dict] = field(default_factory=list)  # List of {page_num, text}
    images: list[ExtractedImage] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    toc: list[dict] = field(default_factory=list)  # Table of contents


class PDFParser:
    """Parser for PDF files using PyMuPDF."""

    def __init__(self, extract_images: bool = True):
        self.extract_images = extract_images

    def parse_file(self, file_path: Path) -> ParsedPDF:
        """Parse a PDF file and extract text, images, and metadata."""
        doc = fitz.open(file_path)

        try:
            # Extract metadata
            metadata = doc.metadata or {}

            # Extract title from metadata or filename
            title = metadata.get("title") or file_path.stem

            # Extract table of contents
            toc = []
            raw_toc = doc.get_toc()
            for level, title_text, page in raw_toc:
                toc.append({
                    "level": level,
                    "title": title_text,
                    "page": page,
                })

            # Extract text from each page
            pages = []
            all_text = []
            images = []

            for page_num in range(len(doc)):
                page = doc[page_num]

                # Extract text
                page_text = page.get_text("text")
                pages.append({
                    "page_num": page_num + 1,
                    "text": page_text,
                })
                all_text.append(page_text)

                # Extract images if enabled
                if self.extract_images:
                    page_images = self._extract_page_images(page, page_num + 1)
                    images.extend(page_images)

            return ParsedPDF(
                title=title,
                text="\n\n".join(all_text),
                page_count=len(doc),
                pages=pages,
                images=images,
                metadata=metadata,
                toc=toc,
            )

        finally:
            doc.close()

    def _extract_page_images(
        self, page: fitz.Page, page_num: int
    ) -> list[ExtractedImage]:
        """Extract images from a PDF page."""
        images = []
        image_list = page.get_images()

        for img_index, img in enumerate(image_list):
            xref = img[0]
            try:
                base_image = page.parent.extract_image(xref)
                if base_image:
                    images.append(ExtractedImage(
                        page_number=page_num,
                        image_bytes=base_image["image"],
                        image_format=base_image["ext"],
                        width=base_image["width"],
                        height=base_image["height"],
                    ))
            except Exception:
                # Skip images that can't be extracted
                continue

        return images

    def extract_text_only(self, file_path: Path) -> str:
        """Quick extraction of just the text content."""
        doc = fitz.open(file_path)
        try:
            text_parts = []
            for page in doc:
                text_parts.append(page.get_text("text"))
            return "\n\n".join(text_parts)
        finally:
            doc.close()

    def get_page_text(self, file_path: Path, page_num: int) -> Optional[str]:
        """Get text from a specific page (1-indexed)."""
        doc = fitz.open(file_path)
        try:
            if 1 <= page_num <= len(doc):
                return doc[page_num - 1].get_text("text")
            return None
        finally:
            doc.close()
