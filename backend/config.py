"""Configuration settings for the Personal Agent."""

from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Paths
    project_root: Path = Path(__file__).parent.parent
    vault_path: Path = Path(__file__).parent.parent / "Obsidian-Neo4j"
    chroma_path: Path = Path(__file__).parent.parent / "data" / "chroma"

    # OpenRouter
    openrouter_api_key: str = ""
    openrouter_model: str = "openai/gpt-5.2-chat"
    openrouter_vision_model: str = "openai/gpt-5.2-chat"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "password123"

    # ChromaDB
    chroma_collection_name: str = "obsidian_notes"
    embedding_model: str = "all-MiniLM-L6-v2"

    # spaCy
    spacy_model: str = "en_core_web_sm"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
