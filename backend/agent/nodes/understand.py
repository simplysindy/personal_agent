"""Understand node - classifies intent and extracts entities."""

import json
import httpx
from typing import Any

from backend.config import settings
from backend.agent.state import AgentState


def understand_node(state: AgentState) -> dict[str, Any]:
    """
    Analyze the user's query to understand intent and extract entities.

    This node:
    1. Classifies the intent (search, explore, add, summarize, reason, general)
    2. Extracts mentioned entities (concepts, people, projects)
    3. Updates state with this information
    """
    query = state.query

    # Use LLM to classify intent and extract entities
    prompt = f"""Analyze this user query about a personal knowledge base.

Query: "{query}"

Classify the intent as one of:
- search: Looking for specific information or documents
- explore: Exploring connections between topics
- add: User wants to add or remember new information
- summarize: Requesting a summary of content
- reason: Requires multi-hop reasoning across multiple documents
- general: General conversation or greeting

Also extract any entities mentioned (names of projects, people, concepts, technologies).

Return JSON:
{{
  "intent": "one of the above",
  "entities": ["entity1", "entity2"],
  "reasoning": "brief explanation"
}}

Return ONLY the JSON."""

    try:
        response = httpx.post(
            f"{settings.openrouter_base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.openrouter_api_key}",
                "HTTP-Referer": "http://localhost:8000",
                "X-Title": "Personal Agent",
            },
            json={
                "model": settings.openrouter_model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 200,
                "temperature": 0.1,
            },
            timeout=30.0,
        )

        if response.status_code == 200:
            data = response.json()
            content = data["choices"][0]["message"]["content"]

            # Parse JSON response
            try:
                # Extract JSON from response
                json_str = content.strip()
                if "```" in json_str:
                    json_str = json_str.split("```")[1]
                    if json_str.startswith("json"):
                        json_str = json_str[4:]
                result = json.loads(json_str)

                return {
                    "intent": result.get("intent", "general"),
                    "entities": result.get("entities", []),
                }
            except json.JSONDecodeError:
                pass

    except Exception as e:
        print(f"Understand node error: {e}")

    # Fallback: simple keyword-based classification
    query_lower = query.lower()

    if any(word in query_lower for word in ["find", "search", "where", "what is"]):
        intent = "search"
    elif any(word in query_lower for word in ["connect", "relate", "how does", "link"]):
        intent = "explore"
    elif any(word in query_lower for word in ["remember", "add", "note", "save"]):
        intent = "add"
    elif any(word in query_lower for word in ["summarize", "summary", "overview"]):
        intent = "summarize"
    elif any(word in query_lower for word in ["why", "explain", "how", "because"]):
        intent = "reason"
    else:
        intent = "general"

    return {
        "intent": intent,
        "entities": [],
    }
