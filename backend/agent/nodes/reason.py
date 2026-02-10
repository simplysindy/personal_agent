"""Reason node - performs multi-hop reasoning over context."""

import json
from typing import Any

import httpx

from backend.config import settings
from backend.agent.state import AgentState


def _format_conversation_history(history) -> str:
    """Format conversation history for the prompt."""
    if not history:
        return ""

    # Limit to last 10 exchanges to avoid token overflow
    recent_history = history[-20:]  # 20 messages = ~10 exchanges

    parts = []
    for msg in recent_history:
        role = "User" if msg.role == "user" else "Assistant"
        parts.append(f"{role}: {msg.content}")

    return "\n".join(parts)


def reason_node(state: AgentState) -> dict[str, Any]:
    """
    Perform reasoning over the retrieved context.

    This node:
    1. Analyzes the context to answer the query
    2. Identifies if more information is needed
    3. Generates intermediate conclusions
    """
    query = state.query
    intent = state.intent
    context = state.context
    reasoning_steps = state.reasoning_steps
    max_steps = state.max_reasoning_steps
    conversation_history = state.conversation_history

    # Format context for the LLM
    context_text = _format_context(context)

    # Format conversation history
    history_text = _format_conversation_history(conversation_history)

    # Check if this is a folder structure query
    has_folder_context = any(
        ctx.source == "folder_structure" for ctx in context
    )

    # Build reasoning prompt based on intent
    if has_folder_context:
        history_section = f"\nPrevious conversation:\n{history_text}\n" if history_text else ""
        prompt = f"""The user is asking about folder/project organization in their knowledge base.
{history_section}
The following shows the actual structure and contents of the relevant folder(s):

{context_text}

User's question: {query}

Based on the folder structure shown above, provide a helpful answer. You can:
- List the files and their types
- Suggest organization improvements if asked
- Highlight patterns in the content
- Note any gaps or areas that could be better organized
Use the conversation history to understand what the user is referring to.

Answer:"""

    elif intent == "search":
        history_section = f"\nPrevious conversation:\n{history_text}\n" if history_text else ""
        prompt = f"""Based on the following context from a personal knowledge base, answer the user's question.
{history_section}
Context:
{context_text}

Current question: {query}

If you can answer directly from the context, provide a clear answer.
If the context doesn't contain enough information, say what's missing.
Cite sources when possible using the file paths provided.
Use the conversation history to understand references like "it", "that", "those", etc.

Answer:"""

    elif intent == "explore":
        history_section = f"\nPrevious conversation:\n{history_text}\n" if history_text else ""
        prompt = f"""The user wants to explore connections in their knowledge base.
{history_section}
Context showing related information:
{context_text}

Current query: {query}

Describe the connections you see between the topics. Highlight:
- Direct relationships
- Indirect connections through shared concepts
- Interesting patterns
Use the conversation history to understand what the user is referring to.

Response:"""

    elif intent == "reason":
        history_section = f"\nPrevious conversation:\n{history_text}\n" if history_text else ""
        prompt = f"""Perform multi-hop reasoning to answer this question using the knowledge base context.
{history_section}
Context:
{context_text}

Current question: {query}

Think step by step:
1. What information do we have?
2. How do the pieces connect?
3. What conclusion can we draw?

If you need more information to complete the reasoning, indicate what's missing.
Use the conversation history to understand references and context.

Reasoning and Answer:"""

    elif intent == "summarize":
        history_section = f"\nPrevious conversation:\n{history_text}\n" if history_text else ""
        prompt = f"""Summarize the following content from the user's knowledge base.
{history_section}
Context:
{context_text}

Summarization request: {query}

Provide a clear, organized summary. Group related information together.
Use the conversation history to understand what the user wants summarized.

Summary:"""

    elif intent == "add":
        prompt = f"""The user wants to add information to their knowledge base.

Their input: {query}

Extract the key information to store:
- Main concept/topic
- Definition or description
- Related concepts
- Any specific details

Return as JSON:
{{
  "concept": "main topic name",
  "description": "what to remember",
  "related_to": ["related concepts"],
  "type": "concept/person/project/note"
}}

JSON:"""

    else:  # general
        history_section = f"\nPrevious conversation:\n{history_text}\n" if history_text else ""
        prompt = f"""You are a helpful assistant with access to a personal knowledge base.
{history_section}
Context from the knowledge base:
{context_text}

Current message: {query}

Respond helpfully. If the context is relevant, incorporate it. If not, just have a normal conversation.
Use the conversation history to understand references and maintain continuity.

Response:"""

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
                "max_tokens": 1000,
                "temperature": 0.7,
            },
            timeout=60.0,
        )

        if response.status_code == 200:
            data = response.json()
            response_text = data["choices"][0]["message"]["content"]

            # Check if more reasoning is needed
            should_continue = False
            if reasoning_steps < max_steps:
                if intent == "reason":
                    # Check if the response indicates need for more info
                    lower_response = response_text.lower()
                    if any(phrase in lower_response for phrase in [
                        "need more information",
                        "missing",
                        "unclear",
                        "cannot determine",
                        "insufficient",
                    ]):
                        should_continue = True

            return {
                "response": response_text,
                "should_continue": should_continue,
                "reasoning_steps": reasoning_steps + 1,
            }

    except Exception as e:
        print(f"Reason node error: {e}")

    return {
        "response": "I encountered an error while processing your request. Please try again.",
        "should_continue": False,
        "reasoning_steps": reasoning_steps + 1,
    }


def _format_context(context) -> str:
    """Format context items for the prompt."""
    if not context:
        return "No relevant context found."

    parts = []
    for i, ctx in enumerate(context, 1):
        # Handle folder structure context specially
        if ctx.source == "folder_structure":
            ctx_type = ctx.metadata.get("type", "folder")
            source_info = f"[FOLDER STRUCTURE: {ctx_type}]"
            parts.append(f"{source_info}\n{ctx.content}\n")
        else:
            source_info = f"[Source {i}: {ctx.source}]"
            if ctx.metadata.get("file_path"):
                source_info = f"[Source {i}: {ctx.metadata['file_path']}]"
            elif ctx.metadata.get("title"):
                source_info = f"[Source {i}: {ctx.metadata['title']}]"

            parts.append(f"{source_info}\n{ctx.content}\n")

    return "\n---\n".join(parts)
