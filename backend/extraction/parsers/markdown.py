"""Markdown file parser using mistune."""

import re
from pathlib import Path
from dataclasses import dataclass, field

import mistune

from .frontmatter import parse_frontmatter


@dataclass
class ParsedMarkdown:
    """Result of parsing a markdown file."""

    title: str
    content: str
    text: str  # Plain text without markdown syntax
    frontmatter: dict = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    links: list[str] = field(default_factory=list)
    wiki_links: list[str] = field(default_factory=list)
    images: list[str] = field(default_factory=list)
    headers: list[dict] = field(default_factory=list)
    code_blocks: list[dict] = field(default_factory=list)


class PlainTextRenderer(mistune.HTMLRenderer):
    """Custom renderer to extract plain text from markdown."""

    def __init__(self):
        super().__init__()
        self.text_parts = []

    def text(self, text):
        self.text_parts.append(text)
        return text

    def paragraph(self, text):
        return text + "\n\n"

    def heading(self, text, level, **attrs):
        return text + "\n\n"

    def list_item(self, text, **attrs):
        return "• " + text + "\n"

    def block_code(self, code, **attrs):
        return code + "\n\n"

    def codespan(self, text):
        return text

    def link(self, text, url, title=None):
        return text

    def image(self, text, url, title=None):
        return f"[Image: {text}]"


class MarkdownParser:
    """Parser for markdown files."""

    def __init__(self):
        self._md = mistune.create_markdown(renderer=PlainTextRenderer())

    def parse_file(self, file_path: Path) -> ParsedMarkdown:
        """Parse a markdown file and extract structured content."""
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        return self.parse_content(content, file_path.stem)

    def parse_content(self, content: str, default_title: str = "Untitled") -> ParsedMarkdown:
        """Parse markdown content string."""
        # Extract frontmatter
        frontmatter, body = parse_frontmatter(content)

        # Extract title from frontmatter or first heading
        title = frontmatter.get("title") or self._extract_title(body) or default_title

        # Extract tags from frontmatter and inline tags
        tags = self._extract_tags(frontmatter, body)

        # Extract various links
        links = self._extract_urls(body)
        wiki_links = self._extract_wiki_links(body)
        images = self._extract_images(body)

        # Extract headers for structure
        headers = self._extract_headers(body)

        # Extract code blocks
        code_blocks = self._extract_code_blocks(body)

        # Convert to plain text
        plain_text = self._to_plain_text(body)

        return ParsedMarkdown(
            title=title,
            content=body,
            text=plain_text,
            frontmatter=frontmatter,
            tags=tags,
            links=links,
            wiki_links=wiki_links,
            images=images,
            headers=headers,
            code_blocks=code_blocks,
        )

    def _extract_title(self, content: str) -> str | None:
        """Extract title from first H1 heading."""
        match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        return match.group(1).strip() if match else None

    def _extract_tags(self, frontmatter: dict, content: str) -> list[str]:
        """Extract tags from frontmatter and inline hashtags."""
        tags = set()

        # From frontmatter
        fm_tags = frontmatter.get("tags", [])
        if isinstance(fm_tags, str):
            tags.add(fm_tags)
        elif isinstance(fm_tags, list):
            tags.update(fm_tags)

        # Inline hashtags (excluding headers)
        inline_tags = re.findall(r'(?<!\S)#([a-zA-Z][a-zA-Z0-9_-]*)\b', content)
        tags.update(inline_tags)

        return list(tags)

    def _extract_urls(self, content: str) -> list[str]:
        """Extract external URLs from markdown links."""
        # Standard markdown links [text](url)
        md_links = re.findall(r'\[([^\]]*)\]\(([^)]+)\)', content)
        urls = [url for _, url in md_links if url.startswith(('http://', 'https://'))]
        return list(set(urls))

    def _extract_wiki_links(self, content: str) -> list[str]:
        """Extract Obsidian-style wiki links [[link]]."""
        # [[link]] or [[link|alias]]
        wiki_links = re.findall(r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]', content)
        return list(set(wiki_links))

    def _extract_images(self, content: str) -> list[str]:
        """Extract image paths from markdown."""
        # Standard markdown images ![alt](path)
        md_images = re.findall(r'!\[[^\]]*\]\(([^)]+)\)', content)

        # Obsidian-style ![[image.png]]
        wiki_images = re.findall(r'!\[\[([^\]]+)\]\]', content)

        return list(set(md_images + wiki_images))

    def _extract_headers(self, content: str) -> list[dict]:
        """Extract all headers with their levels."""
        headers = []
        for match in re.finditer(r'^(#{1,6})\s+(.+)$', content, re.MULTILINE):
            level = len(match.group(1))
            text = match.group(2).strip()
            headers.append({"level": level, "text": text})
        return headers

    def _extract_code_blocks(self, content: str) -> list[dict]:
        """Extract fenced code blocks."""
        code_blocks = []
        pattern = r'```(\w*)\n(.*?)```'
        for match in re.finditer(pattern, content, re.DOTALL):
            language = match.group(1) or "text"
            code = match.group(2).strip()
            code_blocks.append({"language": language, "code": code})
        return code_blocks

    def _to_plain_text(self, content: str) -> str:
        """Convert markdown to plain text."""
        # Remove code blocks first
        text = re.sub(r'```[\s\S]*?```', '', content)

        # Remove inline code
        text = re.sub(r'`[^`]+`', '', text)

        # Remove images
        text = re.sub(r'!\[[^\]]*\]\([^)]+\)', '', text)
        text = re.sub(r'!\[\[[^\]]+\]\]', '', text)

        # Convert links to just text
        text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
        text = re.sub(r'\[\[([^\]|]+)(?:\|([^\]]+))?\]\]', lambda m: m.group(2) or m.group(1), text)

        # Remove markdown formatting
        text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)  # bold
        text = re.sub(r'\*([^*]+)\*', r'\1', text)  # italic
        text = re.sub(r'__([^_]+)__', r'\1', text)  # bold
        text = re.sub(r'_([^_]+)_', r'\1', text)  # italic
        text = re.sub(r'~~([^~]+)~~', r'\1', text)  # strikethrough

        # Remove headers markers
        text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)

        # Remove horizontal rules
        text = re.sub(r'^[-*_]{3,}$', '', text, flags=re.MULTILINE)

        # Remove list markers
        text = re.sub(r'^\s*[-*+]\s+', '', text, flags=re.MULTILINE)
        text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)

        # Remove blockquotes
        text = re.sub(r'^>\s*', '', text, flags=re.MULTILINE)

        # Normalize whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)

        return text.strip()
