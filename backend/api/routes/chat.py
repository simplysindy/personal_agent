"""Chat API routes with WebSocket streaming."""

import json
import asyncio
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel

from backend.agent import AgentGraph


router = APIRouter(prefix="/chat", tags=["chat"])

# Global agent instance
_agent: Optional[AgentGraph] = None


def set_agent(agent: AgentGraph) -> None:
    """Set the agent instance."""
    global _agent
    _agent = agent


class HistoryMessage(BaseModel):
    """A message in the conversation history."""

    role: str  # "user" or "agent"
    content: str


class ChatMessage(BaseModel):
    """Chat message request."""

    message: str
    conversation_id: Optional[str] = None
    history: list[HistoryMessage] = []


class ChatResponse(BaseModel):
    """Chat response."""

    response: str
    intent: str
    sources: list[str] = []
    conversation_id: Optional[str] = None


@router.post("/message", response_model=ChatResponse)
async def send_message(request: ChatMessage) -> ChatResponse:
    """Send a message and get a response."""
    if not _agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    try:
        # Convert history to dicts for the agent
        history = [{"role": h.role, "content": h.content} for h in request.history]
        result = await _agent.ainvoke(request.message, history=history)

        # Extract sources from context
        sources = []
        if result.get("context"):
            for ctx in result["context"]:
                if ctx.metadata.get("file_path"):
                    sources.append(ctx.metadata["file_path"])
                elif ctx.metadata.get("title"):
                    sources.append(ctx.metadata["title"])

        return ChatResponse(
            response=result.get("response", ""),
            intent=result.get("intent", "general"),
            sources=list(set(sources))[:5],
            conversation_id=request.conversation_id,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.websocket("/ws")
async def websocket_chat(websocket: WebSocket):
    """WebSocket endpoint for streaming chat."""
    await websocket.accept()

    if not _agent:
        await websocket.send_json({"error": "Agent not initialized"})
        await websocket.close()
        return

    try:
        while True:
            # Receive message
            data = await websocket.receive_text()
            message_data = json.loads(data)
            query = message_data.get("message", "")

            if not query:
                await websocket.send_json({"error": "Empty message"})
                continue

            # Stream response
            try:
                await websocket.send_json({
                    "type": "start",
                    "message": "Processing...",
                })

                # Stream each step
                async for state in _agent.astream(query):
                    for node_name, node_state in state.items():
                        await websocket.send_json({
                            "type": "step",
                            "node": node_name,
                            "data": _serialize_state(node_state),
                        })

                # Send final response
                await websocket.send_json({
                    "type": "complete",
                    "response": state.get("respond", {}).get("response", ""),
                })

            except Exception as e:
                await websocket.send_json({
                    "type": "error",
                    "error": str(e),
                })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"error": str(e)})
        except:
            pass


def _serialize_state(state) -> dict:
    """Serialize state for JSON transmission."""
    if hasattr(state, "dict"):
        return state.dict()
    if isinstance(state, dict):
        result = {}
        for k, v in state.items():
            if hasattr(v, "dict"):
                result[k] = v.dict()
            elif isinstance(v, list):
                result[k] = [
                    item.dict() if hasattr(item, "dict") else item
                    for item in v
                ]
            else:
                result[k] = v
        return result
    return {"value": str(state)}
