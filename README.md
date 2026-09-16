# Cortex

A stateful AI chatbot built with LangGraph — persistent memory, streaming responses, and
multi-threaded conversations, wired up end to end from a Gemini-backed agent to a Next.js UI.

![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-1C3C3C)
![Next.js](https://img.shields.io/badge/Next.js-15-000000?logo=next.js&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)
![LangSmith](https://img.shields.io/badge/LangSmith-1C3C3C)
![MCP](https://img.shields.io/badge/MCP-000000)

## Tech stack

| Layer            | Technology                                                                 |
| ----------------- | --------------------------------------------------------------------------- |
| Agent / orchestration | [LangGraph](https://langchain-ai.github.io/langgraph/) — async `StateGraph` with an `add_messages` reducer |
| LLM               | [Gemini](https://ai.google.dev/) via `langchain-google-genai`                |
| API               | [FastAPI](https://fastapi.tiangolo.com/) + `uvicorn`, fully async, streaming responses over HTTP |
| Conversation memory | [PostgreSQL](https://www.postgresql.org/) via LangGraph's `AsyncPostgresSaver` checkpointer |
| Observability     | [LangSmith](https://smith.langchain.com/) — traces every graph run, node, and LLM call |
| Tools             | [MCP](https://modelcontextprotocol.io/) servers for web search (DuckDuckGo) and a calculator, called through a LangGraph `ToolNode` |
| Frontend          | [Next.js](https://nextjs.org/) (App Router) + React + TypeScript             |
| Local infra       | Docker Compose (Postgres)                                                    |

## Features

- Token-by-token streaming replies
- Persistent conversation memory per thread, backed by Postgres (survives backend restarts)
- Multi-chat sidebar — create, switch between, and delete independent conversation threads
- Markdown-rendered responses (headings, lists, bold/italic, code, rules) with no external dependency
- End-to-end tracing and observability via LangSmith (graph, node, and LLM-level runs)
- Tool calling — the agent can search the web (DuckDuckGo) and run calculations, with a live
  execution indicator in the UI while a tool is running
- Tools run as standalone MCP servers, not in-process functions — the chatbot backend is an
  MCP client that discovers and calls them over the Model Context Protocol

## Tools

The agent can call tools mid-conversation when it decides it needs them, then use the results to
answer. Each tool is its own MCP server under `backend/mcp_servers/`, and `chatbot.py` connects to
both via `langchain-mcp-adapters`' `MultiServerMCPClient` to discover and bind them at startup:

| Tool               | MCP server                          | Transport                          | Purpose |
| ------------------- | ------------------------------------ | ------------------------------------ | --------- |
| `calculator`        | `mcp_servers/calculator_server.py`  | stdio — spawned by the client automatically, no extra process to run | Arithmetic evaluation (`+ - * / // % **`), via a restricted AST parser — no `eval()` |
| `duckduckgo_search` | `mcp_servers/search_server.py`      | streamable HTTP on `:8100` — must be started as its own process | Web search for current events or facts, via the `ddgs` package (no API key) |

The frontend shows a chip for each tool call as it runs (spinner while in progress, checkmark
when done) above the streamed reply.

## Running locally

**1. Start Postgres** (chat history is persisted here via LangGraph's `AsyncPostgresSaver`):

```bash
docker compose up -d postgres
```

**2. Set environment variables** in `.env` at the repo root:

```bash
GOOGLE_API_KEY=your-gemini-api-key
DATABASE_URL=postgresql://cortex:cortex@localhost:5432/cortex

# optional — enables LangSmith tracing for observability
LANGCHAIN_TRACING_V2=true
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
LANGCHAIN_API_KEY=your-langsmith-api-key
LANGCHAIN_PROJECT=cortex

# optional — override if the search MCP server runs somewhere other than localhost:8100
SEARCH_MCP_URL=http://127.0.0.1:8100/mcp
```

**3. Start the search MCP server, backend, and frontend in three separate terminals:**

```bash
# terminal 1 — DuckDuckGo search MCP server (streamable HTTP, :8100)
cd backend && source ../.venv/bin/activate && python mcp_servers/search_server.py
```

```bash
# terminal 2 — backend API (also spawns the calculator MCP server over stdio)
cd backend && source ../.venv/bin/activate && uvicorn server:app --port 8000
```

```bash
# terminal 3 — frontend (Next.js)
cd frontend && npm install && npm run dev -- --port 5500
```

**4. Open [http://localhost:5500](http://localhost:5500)** in your browser.

The frontend reads the backend URL from `NEXT_PUBLIC_API_URL` (see
`frontend/.env.local.example`); copy it to `.env.local` to override the default of
`http://localhost:8000/chat`.
