import os
import re
import sys
from pathlib import Path

from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Annotated
from langchain_core.messages import BaseMessage, SystemMessage, ToolMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.config import get_config
from langgraph.graph.message import add_messages
from langgraph.prebuilt import tools_condition
from langgraph.types import interrupt
from langchain_core.tools import tool
from langchain_mcp_adapters.client import MultiServerMCPClient
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from ltm import store as ltm_store
from ltm.config import DEFAULT_USER_ID

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
    "say so instead of guessing. Use search_memory to recall known facts about "
    "the user (name, preferences, settings, prior context) whenever they'd help "
    "you personalize or ground your answer — not just when asked directly. Use "
    "save_memory to record durable facts about the user as you learn them — both "
    "when they explicitly ask you to remember something, and proactively when "
    "they mention a stable preference, setting, or fact about themselves worth "
    "recalling in future conversations. Don't save one-off details specific to "
    "this conversation (e.g. today's task) or anything the user says only in "
    "passing — save what would still be true and useful next week."
))


class ChatbotState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


# Tools whose calls pause the graph for a human approve/deny decision before
# they run. Left out: calculator (pure, side-effect-free computation),
# search_memory (pure read).
APPROVAL_REQUIRED_TOOLS = {"duckduckgo_search", "retrieve_documents", "save_memory"}
RETRIEVAL_TOOL = "retrieve_documents"

_CHUNK_BLOCK_RE = re.compile(r"^\[(\d+)\] Source: (.+?)\n([\s\S]*)$")


def _parse_retrieved_chunks(text: str) -> list[dict] | None:
    """Parse rag_server._format_results' output back into structured chunks
    for the retrieval-review UI. Returns None for non-chunk output (the "no
    relevant information" / error strings), which needs no review step."""
    blocks = re.split(r"\n\n(?=\[\d+\] Source: )", text)
    chunks = []
    for block in blocks:
        match = _CHUNK_BLOCK_RE.match(block)
        if not match:
            return None
        chunks.append({"index": int(match.group(1)), "source": match.group(2), "text": match.group(3)})
    return chunks or None


def _make_search_memory_tool(pool: AsyncConnectionPool):
    """Build the search_memory tool bound to this app's connection pool.

    Not an MCP tool (unlike calculator/rag/search) because it needs the
    calling user's identity, which the LLM must never supply itself — it's
    read from the run's `configurable.user_id` via get_config(), the same
    contextvar-based channel LangGraph uses for thread_id, rather than from
    a tool argument the model could spoof or omit.
    """

    @tool
    async def search_memory(query: str) -> str:
        """Search long-term memory for facts about the current user —
        profile info, preferences, settings, and notes from prior sessions.
        Use this to personalize answers or recall context the user hasn't
        restated in this conversation.

        Args:
            query: What to look for, phrased as a natural-language question
                or topic (e.g. "preferred programming language").
        """
        user_id = get_config().get("configurable", {}).get("user_id", DEFAULT_USER_ID)
        results = await ltm_store.search_memory(pool, user_id, query)
        if not results:
            return "No relevant long-term memory found for this user."
        return "\n".join(f"- ({r['category']}) {r['content']}" for r in results)

    return search_memory


def _make_save_memory_tool(pool: AsyncConnectionPool):
    """Build the save_memory tool bound to this app's connection pool.

    Gated behind APPROVAL_REQUIRED_TOOLS — the frontend shows an Allow/Deny
    card with the exact fact before it's written, since writes persist
    across every future session, unlike a read. Scoped to the calling user
    the same way as search_memory (get_config(), never a tool argument).
    """

    @tool
    async def save_memory(content: str, category: str = "fact") -> str:
        """Save a durable fact about the current user to long-term memory,
        for recall in future conversations. Use for things worth remembering
        beyond this conversation — the user's name, preferences, settings,
        or stable context — not one-off details specific to right now.

        If a very similar memory already exists, this updates it in place
        rather than creating a duplicate (e.g. saving a new preferred
        language replaces the old one).

        Args:
            content: The fact to remember, as a short, self-contained
                statement (e.g. "preferred programming language: Rust").
            category: One of "profile" (stable identity facts), "setting"
                (preferences/config), or "note" (other context). Defaults
                to "fact" if unsure.
        """
        user_id = get_config().get("configurable", {}).get("user_id", DEFAULT_USER_ID)
        result = await ltm_store.upsert_memory(pool, user_id, content, category)
        verb = "Updated an existing similar memory" if result["action"] == "updated" else "Saved a new memory"
        return f"{verb}: {content}"

    return save_memory


def _build_graph(tools):
    llm_with_tools = llm.bind_tools(tools)
    tools_by_name = {t.name: t for t in tools}

    async def chat_node(state: ChatbotState):
        messages = state['messages']
        response = await llm_with_tools.ainvoke([SYSTEM_PROMPT, *messages])
        return {'messages': [response]}

    async def execute_tools(state: ChatbotState):
        calls = getattr(state['messages'][-1], "tool_calls", None) or []

        gated = [c for c in calls if c["name"] in APPROVAL_REQUIRED_TOOLS]
        decisions: dict[str, bool] = {}
        if gated:
            reply = interrupt({
                "type": "tool_approval",
                "calls": [{"id": c["id"], "tool": c["name"], "input": c["args"]} for c in gated],
            })
            decisions = (reply or {}).get("decisions", {})

        results = []
        for call in calls:
            if call["name"] in APPROVAL_REQUIRED_TOOLS and not decisions.get(call["id"]):
                results.append(ToolMessage(
                    content="Denied by user — this action was not run.",
                    name=call["name"],
                    tool_call_id=call["id"],
                ))
                continue

            output = await tools_by_name[call["name"]].ainvoke(call["args"])
            output_text = output if isinstance(output, str) else str(output)

            if call["name"] == RETRIEVAL_TOOL:
                chunks = _parse_retrieved_chunks(output_text)
                if chunks:
                    reply = interrupt({
                        "type": "retrieval_review",
                        "tool_call_id": call["id"],
                        "chunks": chunks,
                    })
                    selected = set((reply or {}).get("selected", [c["index"] for c in chunks]))
                    kept = [c for c in chunks if c["index"] in selected]
                    output_text = (
                        "\n\n".join(f"[{c['index']}] Source: {c['source']}\n{c['text']}" for c in kept)
                        if kept else "The user reviewed the retrieved passages and excluded all of them as irrelevant."
                    )

            results.append(ToolMessage(content=output_text, name=call["name"], tool_call_id=call["id"]))

        return {"messages": results}

    graph = StateGraph(ChatbotState)
    graph.add_node('chat_node', chat_node)
    graph.add_node('tools', execute_tools)
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
    HTTP — `docker compose up -d` must already be running the `search`
    container (defaults to http://127.0.0.1:8100/mcp, override via
    SEARCH_MCP_URL).

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
    mcp_tools = await mcp_client.get_tools()

    pool = AsyncConnectionPool(
        conninfo=DATABASE_URL,
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
        open=False,
    )
    await pool.open()
    checkpointer = AsyncPostgresSaver(pool)
    await checkpointer.setup()
    await ltm_store.ensure_schema(pool)

    tools = [*mcp_tools, _make_search_memory_tool(pool), _make_save_memory_tool(pool)]

    graph = _build_graph(tools)
    return graph.compile(checkpointer=checkpointer), pool
