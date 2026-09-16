import os

from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Annotated
from langchain_core.messages import BaseMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from tools import TOOLS

load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]

llm = ChatGoogleGenerativeAI(model = 'gemini-3.6-flash')
llm_with_tools = llm.bind_tools(TOOLS)

class ChatbotState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]

async def chat_node(state: ChatbotState):
    messages = state['messages']
    response = await llm_with_tools.ainvoke(messages)
    return {'messages': [response]}


graph = StateGraph(ChatbotState)
graph.add_node('chat_node', chat_node)
graph.add_node('tools', ToolNode(TOOLS))
graph.add_edge(START, "chat_node")
graph.add_conditional_edges("chat_node", tools_condition, {"tools": "tools", END: END})
graph.add_edge("tools", "chat_node")


async def build_chatbot():
    """Open the async Postgres pool/checkpointer and compile the graph.

    Must be awaited from within a running event loop (e.g. a FastAPI
    lifespan handler) since AsyncConnectionPool.open() requires one.
    Returns (compiled_graph, pool) — the caller owns the pool's lifecycle
    and must await pool.close() on shutdown.
    """
    pool = AsyncConnectionPool(
        conninfo=DATABASE_URL,
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
        open=False,
    )
    await pool.open()
    checkpointer = AsyncPostgresSaver(pool)
    await checkpointer.setup()
    return graph.compile(checkpointer=checkpointer), pool