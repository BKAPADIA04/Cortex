import asyncio
import json
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from langchain_core.messages import HumanMessage

import chatbot
from rag import store
from rag.config import ALLOWED_EXTENSIONS, MAX_FILE_SIZE_BYTES, UPLOAD_DIR
from rag.errors import RagError


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.chatbot, app.state.pool = await chatbot.build_chatbot()
    yield
    await app.state.pool.close()


app = FastAPI(title="Cortex Chat API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    thread_id: str = "default"


class ChatResponse(BaseModel):
    response: str


class DocumentResponse(BaseModel):
    doc_id: str
    filename: str
    chunks: int
    pages: int | None = None


class DocumentSummaryResponse(BaseModel):
    doc_id: str
    filename: str
    chunks: int
    uploaded_at: float


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    config = {"configurable": {"thread_id": request.thread_id}}
    result = await app.state.chatbot.ainvoke(
        {"messages": [HumanMessage(content=request.message)]}, config=config
    )
    return ChatResponse(response=result["messages"][-1].text)


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    config = {"configurable": {"thread_id": request.thread_id}}

    async def event_generator():
        async for mode, chunk in app.state.chatbot.astream(
            {"messages": [HumanMessage(content=request.message)]},
            config=config,
            stream_mode=["updates", "messages"],
        ):
            if mode == "updates":
                for node_name, node_output in chunk.items():
                    for msg in node_output.get("messages", []):
                        if node_name == "chat_node":
                            for call in getattr(msg, "tool_calls", None) or []:
                                yield json.dumps({
                                    "type": "tool_start",
                                    "id": call["id"],
                                    "tool": call["name"],
                                    "input": call["args"],
                                }) + "\n"
                        elif node_name == "tools":
                            yield json.dumps({
                                "type": "tool_end",
                                "id": msg.tool_call_id,
                                "tool": msg.name,
                                "output": msg.text[:2000],
                            }) + "\n"
            elif mode == "messages":
                message_chunk, metadata = chunk
                if metadata.get("langgraph_node") != "chat_node":
                    continue
                text = message_chunk.text
                if text:
                    yield json.dumps({"type": "token", "content": text}) + "\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")


@app.post("/documents", response_model=DocumentResponse)
async def upload_document(file: UploadFile = File(...)):
    filename = file.filename or "upload"
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"File exceeds the {MAX_FILE_SIZE_BYTES // (1024 * 1024)}MB limit.",
        )
    if not contents:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    dest = UPLOAD_DIR / f"{uuid.uuid4().hex}{ext}"
    dest.write_bytes(contents)

    try:
        result = await asyncio.to_thread(store.add_document, dest, filename)
    except RagError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to process '{filename}': {exc}") from exc
    finally:
        dest.unlink(missing_ok=True)

    return DocumentResponse(**result)


@app.get("/documents", response_model=list[DocumentSummaryResponse])
async def list_documents():
    docs = await asyncio.to_thread(store.list_documents)
    return [DocumentSummaryResponse(**d) for d in docs]


@app.delete("/documents/{doc_id}")
async def delete_document(doc_id: str):
    deleted = await asyncio.to_thread(store.delete_document, doc_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found.")
    return {"deleted": doc_id}
