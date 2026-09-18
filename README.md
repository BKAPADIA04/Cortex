# Cortex

A stateful AI chatbot built with LangGraph — persistent memory, streaming responses, and
multi-threaded conversations, wired up end to end from a Gemini-backed agent to a Next.js UI. It
can also answer questions from documents you upload (PDF/DOCX/TXT) via a retrieval-augmented
generation (RAG) pipeline, with source citations, and recall (and, with your approval, save) facts
about the user across sessions via a Postgres-backed long-term memory (LTM) store.

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
| Long-term memory (LTM) | Postgres + [pgvector](https://github.com/pgvector/pgvector) — same database as conversation memory, a second table holding per-user facts, prefilled and agent-written, retrieved (and upserted) by semantic search |
| Observability     | [LangSmith](https://smith.langchain.com/) — traces every graph run, node, and LLM call |
| Tools             | [MCP](https://modelcontextprotocol.io/) servers for web search (DuckDuckGo), a calculator, and document retrieval (RAG), called through a custom tool-executing node with human-in-the-loop approval gates |
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
- Human-in-the-loop controls — the agent pauses for your approval before running a web search,
  document retrieval, or long-term memory write, lets you review and filter retrieved passages
  before it answers from them, and asks for confirmation before deleting an uploaded document. See
  [Human-in-the-loop](#human-in-the-loop) below.
- Long-term memory — the agent can recall facts about the user (profile, preferences, settings)
  across sessions and threads via semantic search over a Postgres/pgvector store, and save new
  ones as it learns them, with your approval before anything is written. See
  [Long-term memory](#long-term-memory-ltm) below.

## Tools

The agent can call tools mid-conversation when it decides it needs them, then use the results to
answer. Each tool is its own MCP server under `backend/mcp_servers/`, and `chatbot.py` connects to
both via `langchain-mcp-adapters`' `MultiServerMCPClient` to discover and bind them at startup:

| Tool               | MCP server                          | Transport                          | Purpose |
| ------------------- | ------------------------------------ | ------------------------------------ | --------- |
| `calculator`        | `mcp_servers/calculator_server.py`  | stdio — spawned by the client automatically, no extra process to run | Arithmetic evaluation (`+ - * / // % **`), via a restricted AST parser — no `eval()` |
| `duckduckgo_search` | `mcp_servers/search_server.py`      | streamable HTTP on `:8100` — runs in its own Docker container (`docker compose up -d`) | Web search for current events or facts, via the `ddgs` package (no API key) |
| `retrieve_documents`, `list_uploaded_documents` | `mcp_servers/rag_server.py` | stdio — spawned by the client automatically, no extra process to run | Search uploaded documents for relevant chunks (with source + page metadata) |
| `search_memory`, `save_memory` | not MCP — plain LangChain tools built in `chatbot.py`, bound directly to the app's Postgres pool | in-process | Semantic search and (approval-gated) upsert over the calling user's long-term memory (see [Long-term memory](#long-term-memory-ltm)) |

`search_memory`/`save_memory` are deliberately not MCP servers like the others: they need to know
which user is asking, and that identity must come from the trusted request context (`user_id` in
`configurable`, via `langgraph.config.get_config()`), never as a tool argument the model could
supply or spoof.

The frontend shows a chip for each tool call as it runs (spinner while in progress, checkmark
when done) above the streamed reply.

## Human-in-the-loop

The agent doesn't act unsupervised. Three checkpoints pause the graph (or the UI) for a human
decision before anything irreversible or externally-visible happens:

1. **Tool-call approval** — before `duckduckgo_search`, `retrieve_documents`, or `save_memory`
   runs, the graph pauses via LangGraph's `interrupt()` and the frontend shows an Allow/Deny card
   for the pending call(s), with the exact content it wants to save for `save_memory`. `calculator`
   and `search_memory` are exempt (pure, side-effect-free reads) and always run immediately.
   Denying a call feeds the agent a `"Denied by user"` tool result instead of executing it, so it
   can adjust its answer accordingly.
2. **Retrieval review** — after `retrieve_documents` is approved and executed, the retrieved
   passages are shown to the user (source + text) before the agent sees them, with a checkbox per
   passage. Only the passages left checked are passed on to the LLM to answer from — excluding all
   of them tells the agent nothing relevant was found.
3. **Document delete confirmation** — removing an uploaded document (the × on its chip) prompts a
   confirmation dialog before the `DELETE /documents/{doc_id}` request fires, since the chunks are
   removed from Chroma permanently.

Implementation:

- **Backend** — `backend/chatbot.py`'s `execute_tools` node (replacing the prebuilt `ToolNode`)
  calls `interrupt()` for gated tools (`APPROVAL_REQUIRED_TOOLS`) and again per
  `retrieve_documents` call to surface its parsed chunks. Interrupts are just another paused graph
  state, persisted by the existing Postgres checkpointer, so they survive backend restarts.
- **API** — `POST /chat/stream` now also emits an `{"type": "interrupt", "payload": {...}}` event
  when the graph pauses; `POST /chat/resume` resumes it with a human decision
  (`{"thread_id": ..., "value": {"decisions": {...}} }` for approvals, `{"selected": [...]}` for
  retrieval review) via LangGraph's `Command(resume=...)`.
- **Frontend** — `frontend/components/InterruptCard.tsx` renders the approval/review UI inline in
  the chat thread; `frontend/components/ConfirmDialog.tsx` is the generic confirm modal used for
  document deletion.

To require approval for additional tools, add their names to `APPROVAL_REQUIRED_TOOLS` in
`backend/chatbot.py`.

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

## Long-term memory (LTM)

Separate from conversation memory (which persists message history per thread) and RAG (which
retrieves from documents you upload), LTM is a store of standing facts about the user — name,
preferences, settings, notes — that the agent can recall in any thread. It starts **prefilled**
(seeded ahead of time from a file you edit) and grows **as the agent learns things**, with your
approval before anything is written.

```text
seed_data.py (edited by you) → python -m ltm.seed ─┐
                                                     ├─→ embed (Gemini) → upsert (Postgres/pgvector)
User says "remember X" / mentions a durable fact ──┘     (near-duplicate in the same category
           → chat_node calls save_memory → approval card  → Allow → upsert                updates
                                                                                            in place;
User Query → chat_node calls search_memory → cosine-similarity search, scoped to the      otherwise
           requesting user_id → matching facts returned to the LLM → personalized answer  inserted)
```

Key pieces:

- **Store** — `backend/ltm/store.py`: `ensure_schema()` creates the `vector` extension, the
  `ltm_memories` table, and a `user_id` index on first run (sizing the vector column from a live
  embedding call rather than a hardcoded dimension). `search_memory()` reads; `upsert_memory()`
  writes — both embed with the same Gemini model the RAG store uses.
- **Writing / dedup** — `upsert_memory()` looks for the nearest existing memory *in the same
  user_id + category* and, if it's within `LTM_DEDUPE_THRESHOLD` (cosine distance), updates that
  row in place instead of inserting a new one — so re-saving "preferred language: Rust" over an
  old "preferred language: Python" replaces it rather than piling up. Category-scoping the match
  matters: plain topical similarity is too coarse on its own (a "name" fact and an unrelated "note"
  can land close together in embedding space just for sharing a subject). Still a similarity
  heuristic, not true conflict detection — it can miss a contradiction worded very differently, or
  merge two same-category rows that are close but distinct.
- **Seeding** — `backend/ltm/seed_data.py` holds the starting facts, grouped by category
  (`profile`, `setting`, `note`); edit that list to change what the bot starts out "remembering,"
  then run:

  ```bash
  cd backend && source ../.venv/bin/activate
  python -m ltm.seed            # load the seed data (upserts — safe to re-run)
  python -m ltm.seed --reset    # wipe existing rows for the seeded users first, then load
  ```

- **Tools** — `search_memory` (always runs, pure read) and `save_memory` (gated — see
  [Human-in-the-loop](#human-in-the-loop)), wired into `chatbot.py`'s tool list (see
  [Tools](#tools)). The system prompt tells the model to search proactively to personalize
  answers, and to save both on explicit request ("remember that...") and proactively when it
  notices a durable fact — but not one-off details specific to the current conversation.
- **Per-user scoping** — every chat request carries a `user_id` (see `ChatRequest` /
  `ChatResumeRequest` in `backend/server.py`, default `"default"`), threaded into the graph's
  `configurable` alongside `thread_id`. Both memory tools read it via `get_config()` at call time,
  so memories stay scoped to whoever is actually asking regardless of which thread they're in.
  **Note:** the frontend doesn't send a real per-user id yet, so all conversations currently share
  the `"default"` memory scope — see [Limitations](#limitations).

## Running locally

**1. Start Postgres and the search MCP server:**

```bash
docker compose up -d
```

This starts Postgres (chat history via LangGraph's `AsyncPostgresSaver`, and long-term memory via
pgvector — the `pgvector/pgvector:pg16` image is plain Postgres 16 with the `vector` extension
built in, not a separate database) and the DuckDuckGo search MCP server (streamable HTTP, `:8100`,
built from `backend/mcp_servers/search.Dockerfile`). The calculator and RAG tools don't need a
container — they run over stdio, spawned automatically by the backend process itself.

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

# optional — LTM tuning (defaults shown)
LTM_EMBEDDING_MODEL=models/gemini-embedding-001
LTM_RETRIEVAL_K=5
LTM_DEDUPE_THRESHOLD=0.28
```

RAG uses `GOOGLE_API_KEY` for embeddings too — no separate credential needed. So does LTM (see
[Long-term memory](#long-term-memory-ltm)); its embedding model defaults to the same
`models/gemini-embedding-001`, overridable via `LTM_EMBEDDING_MODEL`.

**3. Seed long-term memory (optional, one-time):**

```bash
cd backend && source ../.venv/bin/activate && python -m ltm.seed
```

Edit `backend/ltm/seed_data.py` first to change what the bot should recall about the user. Safe to
skip — the chatbot works fine with an empty LTM store, `search_memory` just reports nothing found.

**4. Start the backend and frontend in two separate terminals:**

```bash
# terminal 1 — backend API (also spawns the calculator and RAG MCP servers over stdio)
cd backend && source ../.venv/bin/activate && uvicorn server:app --port 8000
```

```bash
# terminal 2 — frontend (Next.js)
cd frontend && npm install && npm run dev -- --port 5500
```

**5. Open [http://localhost:5500](http://localhost:5500)** in your browser.

Prefer to run the search server locally instead of in Docker (e.g. for debugging)? Run
`cd backend && source ../.venv/bin/activate && python mcp_servers/search_server.py` in its own
terminal instead of step 1's `search` container.

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
- LTM dedup/update is a cosine-similarity heuristic scoped to same user + category — it can miss a
  contradicting fact worded very differently (leaving both the old and new fact stored), or merge
  two distinct facts that happen to be very similar within the same category.
- The frontend doesn't yet send a real per-user identifier, so every conversation currently shares
  the same `"default"` LTM scope — the per-user schema and API are in place, but true isolation
  needs auth (or at least a stable per-browser id) wired up in `frontend/components/ChatApp.tsx`.
