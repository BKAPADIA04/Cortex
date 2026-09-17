import os
import sys
from pathlib import Path

from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Annotated
from langchain_core.messages import BaseMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_mcp_adapters.client import MultiServerMCPClient
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]
SEARCH_MCP_URL = os.environ.get("SEARCH_MCP_URL", "http://127.0.0.1:8100/mcp")
CALCULATOR_SERVER_SCRIPT = str(Path(__file__).parent / "mcp_servers" / "calculator_server.py")
RAG_SERVER_SCRIPT = str(Path(__file__).parent / "mcp_servers" / "rag_server.py")

llm = ChatGoogleGenerativeAI(model = 'gemini-3.6-flash')

SYSTEM_PROMPT = SystemMessage(content=(
    "You are Cortex, a helpful assistant. When you use retrieve_documents to "
    "answer from an uploaded document, cite the source after the relevant "
    "sentence, e.g. (report.pdf, page 3). If retrieval finds nothing relevant, "
    "say so instead of guessing."
))


class ChatbotState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


def _build_graph(tools):
    llm_with_tools = llm.bind_tools(tools)

    async def chat_node(state: ChatbotState):
        messages = state['messages']
        response = await llm_with_tools.ainvoke([SYSTEM_PROMPT, *messages])
        return {'messages': [response]}

    graph = StateGraph(ChatbotState)
    graph.add_node('chat_node', chat_node)
    graph.add_node('tools', ToolNode(tools))
    graph.add_edge(START, "chat_node")
    graph.add_conditional_edges("chat_node", tools_condition, {"tools": "tools", END: END})
    graph.add_edge("tools", "chat_node")
    return graph


async def build_chatbot():
    """Connect to the MCP tool servers, open the Postgres pool/checkpointer,
    and compile the graph.

    Must be awaited from within a running event loop (e.g. a FastAPI
    lifespan handler). The calculator and RAG retrieval tools are served
    over stdio — the MCP client spawns their scripts itself, per call, no
    separate process to run. The search tool is served over streamable
    HTTP — `mcp_servers/search_server.py` must already be running
    (defaults to http://127.0.0.1:8100/mcp, override via SEARCH_MCP_URL).

    Returns (compiled_graph, pool) — the caller owns the pool's lifecycle
    and must await pool.close() on shutdown.
    """
    mcp_client = MultiServerMCPClient({
        "calculator": {
            "transport": "stdio",
            "command": sys.executable,
            "args": [CALCULATOR_SERVER_SCRIPT],
        },
        "rag": {
            "transport": "stdio",
            "command": sys.executable,
            "args": [RAG_SERVER_SCRIPT],
        },
        "search": {
            "transport": "streamable_http",
            "url": SEARCH_MCP_URL,
        },
    })
    tools = await mcp_client.get_tools()

    pool = AsyncConnectionPool(
        conninfo=DATABASE_URL,
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
        open=False,
    )
    await pool.open()
    checkpointer = AsyncPostgresSaver(pool)
    await checkpointer.setup()

    graph = _build_graph(tools)
    return graph.compile(checkpointer=checkpointer), pool
