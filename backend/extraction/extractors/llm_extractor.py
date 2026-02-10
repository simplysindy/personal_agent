"""LLM-based extraction using OpenRouter."""

import json
from typing import Optional
from dataclasses import dataclass, field

import httpx

from backend.config import settings


@dataclass
class LLMExtractedContent:
    """Content extracted via LLM."""

    summary: str = ""
    concepts: list[dict] = field(default_factory=list)
    relationships: list[dict] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    key_insights: list[str] = field(default_factory=list)


class LLMExtractor:
    """Extract structured information using LLM via OpenRouter."""

    def __init__(
        self,
        api_key: str = None,
        model: str = None,
        base_url: str = None,
    ):
        self.api_key = api_key or settings.openrouter_api_key
        self.model = model or settings.openrouter_model
        self.base_url = base_url or settings.openrouter_base_url

    def _call_llm(self, prompt: str, max_tokens: int = 1000) -> Optional[str]:
        """Make a call to the LLM via OpenRouter."""
        if not self.api_key:
            return None

        try:
            response = httpx.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "HTTP-Referer": "http://localhost:8000",
                    "X-Title": "Personal Agent",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a knowledge extraction assistant. Extract structured information from text and return it in the exact JSON format requested. Be concise and precise.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": max_tokens,
                    "temperature": 0.1,
                },
                timeout=60.0,
            )

            if response.status_code == 200:
                data = response.json()
                return data["choices"][0]["message"]["content"]
            return None

        except Exception as e:
            print(f"LLM call failed: {e}")
            return None

    def extract(self, text: str, title: str = "") -> LLMExtractedContent:
        """Extract structured content from text using LLM."""
        result = LLMExtractedContent()

        # Truncate text if too long
        text = text[:8000]

        # Extract summary and concepts
        prompt = f"""Analyze this document and extract structured information.

Title: {title}

Content:
{text}

Return a JSON object with these fields:
{{
  "summary": "A 2-3 sentence summary of the document",
  "concepts": [
    {{"name": "concept name", "definition": "brief definition", "importance": "high/medium/low"}}
  ],
  "topics": ["topic1", "topic2"],
  "key_insights": ["insight1", "insight2"]
}}

Return ONLY the JSON, no other text."""

        response = self._call_llm(prompt, max_tokens=1500)

        if response:
            try:
                # Extract JSON from response
                json_str = self._extract_json(response)
                data = json.loads(json_str)

                result.summary = data.get("summary", "")
                result.concepts = data.get("concepts", [])
                result.topics = data.get("topics", [])
                result.key_insights = data.get("key_insights", [])

            except json.JSONDecodeError:
                # If JSON parsing fails, try to extract summary at least
                result.summary = response[:500] if len(response) < 1000 else ""

        return result

    def extract_relationships(
        self,
        text: str,
        known_entities: list[str] = None,
    ) -> list[dict]:
        """Extract relationships between entities."""
        known = known_entities or []
        known_str = ", ".join(known[:20]) if known else "any entities you identify"

        prompt = f"""From this text, identify relationships between entities.
Known entities: {known_str}

Text:
{text[:4000]}

Return a JSON array of relationships:
[
  {{"source": "Entity A", "target": "Entity B", "relationship": "relationship type", "description": "brief description"}}
]

Focus on meaningful relationships like:
- Uses/implements (technologies)
- Works with/collaborates
- Part of/belongs to
- Related to/similar to

Return ONLY the JSON array, no other text."""

        response = self._call_llm(prompt, max_tokens=1000)

        if response:
            try:
                json_str = self._extract_json(response)
                relationships = json.loads(json_str)
                if isinstance(relationships, list):
                    return relationships
            except json.JSONDecodeError:
                pass

        return []

    def generate_document_summary(self, text: str, title: str = "") -> str:
        """Generate a concise summary of a document."""
        prompt = f"""Summarize this document in 2-3 sentences. Focus on the main topic and key points.

Title: {title}

Content:
{text[:6000]}

Return ONLY the summary, no other text."""

        response = self._call_llm(prompt, max_tokens=200)
        return response.strip() if response else ""

    def suggest_related_concepts(
        self,
        concepts: list[str],
        context: str = "",
    ) -> list[dict]:
        """Suggest related concepts based on existing ones."""
        concepts_str = ", ".join(concepts[:10])

        prompt = f"""Given these concepts: {concepts_str}

Context: {context[:2000]}

Suggest related concepts that might connect these together.
Return a JSON array:
[
  {{"concept": "name", "relation_to": "existing concept", "why": "brief reason"}}
]

Return ONLY the JSON array."""

        response = self._call_llm(prompt, max_tokens=500)

        if response:
            try:
                json_str = self._extract_json(response)
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass

        return []

    def _extract_json(self, text: str) -> str:
        """Extract JSON from text that might have other content."""
        # Try to find JSON object or array
        text = text.strip()

        # If it starts with { or [, assume it's JSON
        if text.startswith(("{", "[")):
            # Find matching end
            depth = 0
            in_string = False
            escape = False

            for i, char in enumerate(text):
                if escape:
                    escape = False
                    continue
                if char == "\\":
                    escape = True
                    continue
                if char == '"' and not escape:
                    in_string = not in_string
                    continue
                if in_string:
                    continue
                if char in "{[":
                    depth += 1
                elif char in "}]":
                    depth -= 1
                    if depth == 0:
                        return text[: i + 1]

        # Try to find JSON in markdown code block
        import re
        json_match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\}|\[[\s\S]*?\])\s*```", text)
        if json_match:
            return json_match.group(1)

        return text
