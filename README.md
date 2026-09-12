# Cortex

A stateful AI chatbot built with LangGraph, featuring memory, RAG, and tool calling.

## Running locally

Start the backend and frontend in two separate terminals:

```
# terminal 1 — backend API
cd backend && source ../.venv/bin/activate && uvicorn server:app --port 8000
```

```
# terminal 2 — frontend (Next.js)
cd frontend && npm install && npm run dev -- --port 5500
```

Then open http://localhost:5500 in your browser. The frontend reads the backend URL from
`NEXT_PUBLIC_API_URL` (see `frontend/.env.local.example`); copy it to `.env.local` to override
the default of `http://localhost:8000/chat`.
