import json
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from langchain_core.messages import HumanMessage

import chatbot


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
                                "output": str(msg.content)[:2000],
                            }) + "\n"
            elif mode == "messages":
                message_chunk, metadata = chunk
                if metadata.get("langgraph_node") != "chat_node":
                    continue
                text = message_chunk.text
                if text:
                    yield json.dumps({"type": "token", "content": text}) + "\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")
