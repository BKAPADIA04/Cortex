# Cortex

A stateful AI chatbot built with LangGraph, featuring memory, RAG, and tool calling.

## Running locally

Start the backend and frontend in two separate terminals:

```
# terminal 1 — backend API
cd backend && source ../.venv/bin/activate && uvicorn server:app --port 8000
```

```
# terminal 2 — frontend
cd frontend && python3 -m http.server 5500
```

Then open http://localhost:5500 in your browser.
