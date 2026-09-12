# Cortex

A stateful AI chatbot built with LangGraph — persistent memory, streaming responses, and
multi-threaded conversations, wired up end to end from a Gemini-backed agent to a Next.js UI.

![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-1C3C3C)
![Next.js](https://img.shields.io/badge/Next.js-15-000000?logo=next.js&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)

## Tech stack

| Layer            | Technology                                                                 |
| ----------------- | --------------------------------------------------------------------------- |
| Agent / orchestration | [LangGraph](https://langchain-ai.github.io/langgraph/) — `StateGraph` with an `add_messages` reducer |
| LLM               | [Gemini](https://ai.google.dev/) via `langchain-google-genai`                |
| API               | [FastAPI](https://fastapi.tiangolo.com/) + `uvicorn`, streaming responses over HTTP |
| Conversation memory | [PostgreSQL](https://www.postgresql.org/) via LangGraph's `PostgresSaver` checkpointer |
| Frontend          | [Next.js](https://nextjs.org/) (App Router) + React + TypeScript             |
| Local infra       | Docker Compose (Postgres)                                                    |

## Features

- Token-by-token streaming replies
- Persistent conversation memory per thread, backed by Postgres (survives backend restarts)
- Multi-chat sidebar — create, switch between, and delete independent conversation threads
- Markdown-rendered responses (headings, lists, bold/italic, code, rules) with no external dependency

## Running locally

**1. Start Postgres** (chat history is persisted here via LangGraph's `PostgresSaver`):

```bash
docker compose up -d postgres
```

**2. Set environment variables** in `.env` at the repo root:

```bash
GOOGLE_API_KEY=your-gemini-api-key
DATABASE_URL=postgresql://cortex:cortex@localhost:5432/cortex
```

**3. Start the backend and frontend in two separate terminals:**

```bash
# terminal 1 — backend API
cd backend && source ../.venv/bin/activate && uvicorn server:app --port 8000
```

```bash
# terminal 2 — frontend (Next.js)
cd frontend && npm install && npm run dev -- --port 5500
```

**4. Open [http://localhost:5500](http://localhost:5500)** in your browser.

The frontend reads the backend URL from `NEXT_PUBLIC_API_URL` (see
`frontend/.env.local.example`); copy it to `.env.local` to override the default of
`http://localhost:8000/chat`.
