import asyncio
import os

from ddgs import DDGS
from mcp.server.fastmcp import FastMCP

# Defaults to localhost-only for a bare `python search_server.py` run; the
# Docker image overrides this to 0.0.0.0 so the container's published port
# is reachable from the host.
SEARCH_MCP_HOST = os.environ.get("SEARCH_MCP_HOST", "127.0.0.1")

mcp = FastMCP("cortex-search", host=SEARCH_MCP_HOST, port=8100)


def _search_sync(query: str) -> list[dict]:
    with DDGS() as ddgs:
        return list(ddgs.text(query, max_results=5))


@mcp.tool()
async def duckduckgo_search(query: str) -> str:
    """Search the web via DuckDuckGo for current or factual information.

    Use this when the user asks about recent events, facts you're unsure
    of, or anything that benefits from up-to-date web results.
    """
    results = await asyncio.to_thread(_search_sync, query)

    if not results:
        return "No results found."

    return "\n\n".join(
        f"{r['title']}\n{r['href']}\n{r['body']}" for r in results
    )


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
