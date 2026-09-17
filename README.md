# Cortex

A stateful AI chatbot built with LangGraph — persistent memory, streaming responses, and
multi-threaded conversations, wired up end to end from a Gemini-backed agent to a Next.js UI. It
can also answer questions from documents you upload (PDF/DOCX/TXT) via a retrieval-augmented
generation (RAG) pipeline, with source citations.

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
| Tools             | [MCP](https://modelcontextprotocol.io/) servers for web search (DuckDuckGo), a calculator, and document retrieval (RAG), called through a LangGraph `ToolNode` |
| RAG / vector store | [Chroma](https://www.trychroma.com/) (local, persisted to disk) via `langchain-chroma`, chunked with `langchain-text-splitters`, embedded with `langchain-google-genai` |
| Document parsing  | `pypdf` (PDF, per-page), `python-docx` (DOCX), built-in (TXT)                |
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
- Upload PDF/DOCX/TXT documents (button next to the chat input) and ask questions about them —
  the agent retrieves relevant chunks and cites the source document (and page, for PDFs) in its
  answer. The chatbot works exactly as before when no document is uploaded.

## Tools

The agent can call tools mid-conversation when it decides it needs them, then use the results to
answer. Each tool is its own MCP server under `backend/mcp_servers/`, and `chatbot.py` connects to
both via `langchain-mcp-adapters`' `MultiServerMCPClient` to discover and bind them at startup:

| Tool               | MCP server                          | Transport                          | Purpose |
| ------------------- | ------------------------------------ | ------------------------------------ | --------- |
| `calculator`        | `mcp_servers/calculator_server.py`  | stdio — spawned by the client automatically, no extra process to run | Arithmetic evaluation (`+ - * / // % **`), via a restricted AST parser — no `eval()` |
| `duckduckgo_search` | `mcp_servers/search_server.py`      | streamable HTTP on `:8100` — must be started as its own process | Web search for current events or facts, via the `ddgs` package (no API key) |
| `retrieve_documents`, `list_uploaded_documents` | `mcp_servers/rag_server.py` | stdio — spawned by the client automatically, no extra process to run | Search uploaded documents for relevant chunks (with source + page metadata) |

The frontend shows a chip for each tool call as it runs (spinner while in progress, checkmark
when done) above the streamed reply.

## Document upload & RAG

Click the attach button next to the chat input to upload a PDF, DOCX, or TXT file. The upload
pipeline runs synchronously and returns a chunk count once indexed:

```text
Upload → Parse (pypdf / python-docx / plain text)
       → Chunk (RecursiveCharacterTextSplitter, ~1000 chars, 150 overlap)
       → Embed (Gemini text-embedding-004)
       → Store (Chroma, persisted under backend/rag_data/)

User Query → chat_node decides to call retrieve_documents → similarity search
           → chunks (+ source, page) returned to the LLM → cited answer
```

Key pieces:

- **Backend API** — `POST /documents` (upload), `GET /documents` (list), `DELETE /documents/{doc_id}`
  (remove), all in `backend/server.py`.
- **Pipeline** — `backend/rag/` (`loaders.py` parsing, `store.py` chunking/embedding/Chroma access
  and the `Retriever` interface, `config.py` tunables, `errors.py` typed exceptions).
- **Tool** — `backend/mcp_servers/rag_server.py` exposes `retrieve_documents` (similarity search,
  optionally scoped to one document by filename) and `list_uploaded_documents` as MCP tools; the
  agent decides on its own when to call them, same as the calculator or web search.
- **Multiple documents** — every chunk is tagged with `doc_id`/`source`/`page` metadata; retrieval
  runs against the whole store by default, or can be scoped to one document by filename.
- **Citations** — a system prompt tells the model to cite `(filename, page N)` when it answers from
  retrieved chunks; the tool's output is pre-formatted with that citation on each chunk.
- **No document uploaded** — the chatbot behaves exactly as before; `retrieve_documents` just
  reports there's nothing to search.
- **Extensibility** — retrieval goes through a small `Retriever` protocol in `rag/store.py`
  (`get_retriever()`), so hybrid (keyword + vector) search, reranking, or a Graph RAG traversal can
  be swapped in later without touching the upload API or the MCP tool.

Uploaded files are written to `backend/rag_data/uploads/` only long enough to parse, then deleted;
the Chroma index persists under `backend/rag_data/chroma/` (gitignored).

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

# optional — RAG tuning (defaults shown)
RAG_DATA_DIR=./backend/rag_data     # where uploads + the Chroma index are stored
RAG_MAX_FILE_SIZE_MB=20
RAG_CHUNK_SIZE=1000
RAG_CHUNK_OVERLAP=150
RAG_RETRIEVAL_K=4
RAG_EMBEDDING_MODEL=models/gemini-embedding-001
```

RAG uses `GOOGLE_API_KEY` for embeddings too — no separate credential needed.

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

## Testing

```bash
cd backend && source ../.venv/bin/activate && python -m pytest
```

Covers document parsing (`tests/test_rag_loaders.py`), the vector store pipeline — add/retrieve/
list/delete, per-document filtering (`tests/test_rag_store.py`), the upload/list/delete API
(`tests/test_upload_api.py`), and the retrieval tool's citation formatting
(`tests/test_rag_server.py`). Tests run against a throwaway Chroma directory with a fake, offline
embeddings stub — no `GOOGLE_API_KEY` or network access required.

## Limitations

- Retrieval is plain vector similarity search — no hybrid keyword search, reranking, or Graph RAG
  yet (the `Retriever` interface in `rag/store.py` is designed so these can be added later).
- DOCX/TXT files don't have a page concept, so citations for them include the filename only, not a
  page number.
- The vector store is a single shared collection — there's no per-user or per-thread isolation of
  uploaded documents.
- Large PDFs are parsed synchronously inside the upload request; very large files will make the
  upload call slow rather than returning immediately and processing in the background.
