"""LangGraph agent definition."""

from typing import Literal

from langgraph.graph import StateGraph, END

from backend.knowledge.graph_store import GraphStore
from backend.knowledge.vector_store import VectorStore

from .state import AgentState, ConversationMessage
from .nodes import understand_node, retrieve_node, reason_node, respond_node
from .nodes.retrieve import set_stores as set_retrieve_stores
from .tools.graph_query import set_graph_store
from .tools.vector_search import set_vector_store
from .tools.add_knowledge import set_stores as set_add_stores
from .tools.folder_structure import set_graph_store as set_folder_graph_store


def should_continue_reasoning(state: AgentState) -> Literal["retrieve", "respond"]:
    """Determine if we should continue reasoning or respond."""
    if state.should_continue and state.reasoning_steps < state.max_reasoning_steps:
        return "retrieve"
    return "respond"


def create_agent_graph(
    graph_store: GraphStore = None,
    vector_store: VectorStore = None,
) -> StateGraph:
    """
    Create the LangGraph agent for knowledge interaction.

    The agent follows this flow:
    1. UNDERSTAND: Classify intent and extract entities
    2. RETRIEVE: Fetch relevant context from graph and vector stores
    3. REASON: Analyze context and generate response
    4. RESPOND: Format and return final response

    For complex queries, it may loop back from REASON to RETRIEVE.
    """
    # Initialize stores
    if graph_store is None:
        graph_store = GraphStore()
        graph_store.connect()

    if vector_store is None:
        vector_store = VectorStore()
        vector_store.connect()

    # Set stores for nodes and tools
    set_retrieve_stores(graph_store, vector_store)
    set_graph_store(graph_store)
    set_vector_store(vector_store)
    set_add_stores(graph_store, vector_store)
    set_folder_graph_store(graph_store)

    # Build the graph
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("understand", understand_node)
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("reason", reason_node)
    workflow.add_node("respond", respond_node)

    # Set entry point
    workflow.set_entry_point("understand")

    # Add edges
    workflow.add_edge("understand", "retrieve")
    workflow.add_edge("retrieve", "reason")

    # Conditional edge from reason
    workflow.add_conditional_edges(
        "reason",
        should_continue_reasoning,
        {
            "retrieve": "retrieve",
            "respond": "respond",
        },
    )

    # End after respond
    workflow.add_edge("respond", END)

    return workflow.compile()


class AgentGraph:
    """Wrapper for the agent graph with convenient methods."""

    def __init__(
        self,
        graph_store: GraphStore = None,
        vector_store: VectorStore = None,
    ):
        self.graph_store = graph_store or GraphStore()
        self.vector_store = vector_store or VectorStore()
        self._graph = None
        self._initialized = False

    def initialize(self) -> None:
        """Initialize stores and compile graph."""
        if not self._initialized:
            self.graph_store.connect()
            self.vector_store.connect()
            self._graph = create_agent_graph(self.graph_store, self.vector_store)
            self._initialized = True

    @property
    def graph(self):
        """Get the compiled graph, initializing if needed."""
        if not self._initialized:
            self.initialize()
        return self._graph

    def invoke(self, query: str, history: list[dict] = None) -> dict:
        """
        Run the agent with a query.

        Args:
            query: User's question or request
            history: Optional conversation history

        Returns:
            Final state including response
        """
        conversation_history = []
        if history:
            conversation_history = [
                ConversationMessage(role=h["role"], content=h["content"])
                for h in history
            ]
        initial_state = AgentState(query=query, conversation_history=conversation_history)
        result = self.graph.invoke(initial_state)
        return result

    async def ainvoke(self, query: str, history: list[dict] = None) -> dict:
        """
        Run the agent asynchronously.

        Args:
            query: User's question or request
            history: Optional conversation history

        Returns:
            Final state including response
        """
        conversation_history = []
        if history:
            conversation_history = [
                ConversationMessage(role=h["role"], content=h["content"])
                for h in history
            ]
        initial_state = AgentState(query=query, conversation_history=conversation_history)
        result = await self.graph.ainvoke(initial_state)
        return result

    def stream(self, query: str):
        """
        Stream agent execution steps.

        Args:
            query: User's question or request

        Yields:
            State updates as the agent progresses
        """
        initial_state = AgentState(query=query)
        for state in self.graph.stream(initial_state):
            yield state

    async def astream(self, query: str):
        """
        Stream agent execution steps asynchronously.

        Args:
            query: User's question or request

        Yields:
            State updates as the agent progresses
        """
        initial_state = AgentState(query=query)
        async for state in self.graph.astream(initial_state):
            yield state

    def close(self) -> None:
        """Close database connections."""
        self.graph_store.close()
