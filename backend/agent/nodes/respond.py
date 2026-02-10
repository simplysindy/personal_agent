"""Respond node - formats final response."""

from typing import Any
from langchain_core.messages import AIMessage

from backend.agent.state import AgentState


def respond_node(state: AgentState) -> dict[str, Any]:
    """
    Format and return the final response.

    This node:
    1. Formats the response for the user
    2. Adds source citations
    3. Creates the final message
    """
    response = state.response
    context = state.context
    intent = state.intent

    # Add source references for search and explore intents
    if intent in ("search", "explore", "reason") and context:
        sources = _extract_sources(context)
        if sources:
            response += "\n\n**Sources:**\n"
            for source in sources[:5]:
                response += f"- {source}\n"

    # Create AI message for the conversation
    message = AIMessage(content=response)

    return {
        "messages": [message],
    }


def _extract_sources(context) -> list[str]:
    """Extract unique sources from context."""
    sources = set()

    for ctx in context:
        if ctx.metadata.get("file_path"):
            sources.add(ctx.metadata["file_path"])
        elif ctx.metadata.get("title"):
            sources.add(ctx.metadata["title"])
        elif ctx.metadata.get("label"):
            name = ctx.content.split("\n")[0] if ctx.content else "Unknown"
            sources.add(f"{ctx.metadata['label']}: {name[:50]}")

    return list(sources)
