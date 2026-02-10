"""Agent state definitions."""

from typing import Annotated, Literal, Optional, Sequence
from pydantic import BaseModel, Field
from langgraph.graph.message import add_messages


class RetrievedContext(BaseModel):
    """Context retrieved from knowledge stores."""

    source: str  # "graph" or "vector"
    content: str
    metadata: dict = Field(default_factory=dict)
    score: float = 0.0


class GraphPath(BaseModel):
    """A path through the knowledge graph."""

    nodes: list[dict] = Field(default_factory=list)
    relationships: list[str] = Field(default_factory=list)


class ConversationMessage(BaseModel):
    """A message in the conversation history."""

    role: str  # "user" or "agent"
    content: str


class AgentState(BaseModel):
    """State for the knowledge agent."""

    # Messages in the conversation
    messages: Annotated[list, add_messages] = Field(default_factory=list)

    # Conversation history from frontend
    conversation_history: list[ConversationMessage] = Field(default_factory=list)

    # Current user query
    query: str = ""

    # Classified intent
    intent: Literal[
        "search",  # Looking for specific information
        "explore",  # Exploring connections
        "add",  # Adding new knowledge
        "summarize",  # Summarizing content
        "reason",  # Multi-hop reasoning
        "general",  # General conversation
    ] = "general"

    # Retrieved context
    context: list[RetrievedContext] = Field(default_factory=list)

    # Graph paths found during reasoning
    graph_paths: list[GraphPath] = Field(default_factory=list)

    # Entities mentioned in query
    entities: list[str] = Field(default_factory=list)

    # Response to return
    response: str = ""

    # Whether to continue reasoning
    should_continue: bool = False

    # Number of reasoning steps taken
    reasoning_steps: int = 0

    # Maximum reasoning steps
    max_reasoning_steps: int = 3

    class Config:
        arbitrary_types_allowed = True
