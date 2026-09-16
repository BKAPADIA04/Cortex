import asyncio

from ddgs import DDGS
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("cortex-search", host="127.0.0.1", port=8100)


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
