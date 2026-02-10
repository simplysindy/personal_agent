"""NLP-based entity extraction using spaCy."""

from dataclasses import dataclass, field
from typing import Optional

import spacy
from spacy.language import Language

from backend.config import settings


@dataclass
class ExtractedEntities:
    """Entities extracted via NLP."""

    people: list[dict] = field(default_factory=list)
    organizations: list[dict] = field(default_factory=list)
    locations: list[dict] = field(default_factory=list)
    technologies: list[dict] = field(default_factory=list)
    dates: list[dict] = field(default_factory=list)
    key_phrases: list[str] = field(default_factory=list)


class NLPExtractor:
    """Extract entities from text using spaCy."""

    # Technology-related keywords to enhance detection
    TECH_KEYWORDS = {
        "python", "javascript", "typescript", "react", "vue", "angular",
        "node", "nodejs", "docker", "kubernetes", "aws", "azure", "gcp",
        "api", "rest", "graphql", "sql", "nosql", "mongodb", "postgresql",
        "redis", "neo4j", "chromadb", "langchain", "langgraph", "openai",
        "llm", "ml", "ai", "machine learning", "deep learning", "nlp",
        "fastapi", "flask", "django", "express", "git", "github",
        "ci/cd", "terraform", "linux", "nginx", "apache",
    }

    def __init__(self, model_name: str = None):
        self._nlp: Optional[Language] = None
        self._model_name = model_name or settings.spacy_model

    def _load_model(self) -> Language:
        """Load spaCy model, downloading if necessary."""
        if self._nlp is None:
            try:
                self._nlp = spacy.load(self._model_name)
            except OSError:
                # Model not found, download it
                from spacy.cli import download
                download(self._model_name)
                self._nlp = spacy.load(self._model_name)
        return self._nlp

    def extract(self, text: str) -> ExtractedEntities:
        """Extract entities from text."""
        nlp = self._load_model()
        doc = nlp(text[:100000])  # Limit text length for performance

        result = ExtractedEntities()

        # Extract named entities
        for ent in doc.ents:
            entity_info = {
                "text": ent.text,
                "start": ent.start_char,
                "end": ent.end_char,
                "label": ent.label_,
            }

            if ent.label_ == "PERSON":
                result.people.append(entity_info)
            elif ent.label_ == "ORG":
                result.organizations.append(entity_info)
            elif ent.label_ in ("GPE", "LOC"):
                result.locations.append(entity_info)
            elif ent.label_ == "DATE":
                result.dates.append(entity_info)
            elif ent.label_ in ("PRODUCT", "WORK_OF_ART"):
                # Could be technology
                if ent.text.lower() in self.TECH_KEYWORDS:
                    result.technologies.append(entity_info)

        # Extract technology mentions from text
        text_lower = text.lower()
        for tech in self.TECH_KEYWORDS:
            if tech in text_lower:
                result.technologies.append({
                    "text": tech,
                    "label": "TECHNOLOGY",
                })

        # Deduplicate
        result.technologies = self._deduplicate_entities(result.technologies)
        result.people = self._deduplicate_entities(result.people)
        result.organizations = self._deduplicate_entities(result.organizations)

        # Extract key noun phrases
        result.key_phrases = self._extract_key_phrases(doc)

        return result

    def _deduplicate_entities(self, entities: list[dict]) -> list[dict]:
        """Remove duplicate entities by text (case-insensitive)."""
        seen = set()
        unique = []
        for ent in entities:
            key = ent["text"].lower()
            if key not in seen:
                seen.add(key)
                unique.append(ent)
        return unique

    def _extract_key_phrases(self, doc, max_phrases: int = 20) -> list[str]:
        """Extract key noun phrases from document."""
        phrases = []

        for chunk in doc.noun_chunks:
            # Filter out very short or very long phrases
            if 2 <= len(chunk.text.split()) <= 5:
                # Filter out phrases that are just pronouns or determiners
                root = chunk.root
                if root.pos_ in ("NOUN", "PROPN"):
                    phrases.append(chunk.text)

        # Deduplicate and limit
        seen = set()
        unique_phrases = []
        for phrase in phrases:
            key = phrase.lower()
            if key not in seen:
                seen.add(key)
                unique_phrases.append(phrase)
                if len(unique_phrases) >= max_phrases:
                    break

        return unique_phrases

    def extract_summary_entities(self, text: str) -> dict:
        """Quick extraction of just entity counts and top entities."""
        entities = self.extract(text)
        return {
            "people_count": len(entities.people),
            "top_people": [p["text"] for p in entities.people[:5]],
            "organizations_count": len(entities.organizations),
            "top_organizations": [o["text"] for o in entities.organizations[:5]],
            "technologies": [t["text"] for t in entities.technologies[:10]],
            "key_phrases": entities.key_phrases[:10],
        }
