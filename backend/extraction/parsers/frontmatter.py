"""YAML frontmatter parser for markdown files."""

import re
import yaml
from typing import Tuple


def parse_frontmatter(content: str) -> Tuple[dict, str]:
    """
    Parse YAML frontmatter from markdown content.

    Returns:
        Tuple of (frontmatter_dict, remaining_content)
    """
    frontmatter_pattern = r'^---\s*\n(.*?)\n---\s*\n'
    match = re.match(frontmatter_pattern, content, re.DOTALL)

    if match:
        try:
            frontmatter = yaml.safe_load(match.group(1)) or {}
            remaining_content = content[match.end():]
            return frontmatter, remaining_content
        except yaml.YAMLError:
            return {}, content

    return {}, content
