from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from langchain_core.messages import HumanMessage

from chatbot import cortex_chatbot

app = FastAPI(title="Cortex Chat API")

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
def chat(request: ChatRequest):
    config = {"configurable": {"thread_id": request.thread_id}}
    result = cortex_chatbot.invoke(
        {"messages": [HumanMessage(content=request.message)]}, config=config
    )
    return ChatResponse(response=result["messages"][-1].text)


@app.post("/chat/stream")
def chat_stream(request: ChatRequest):
    config = {"configurable": {"thread_id": request.thread_id}}

    def token_generator():
        for message_chunk, metadata in cortex_chatbot.stream(
            {"messages": [HumanMessage(content=request.message)]},
            config=config,
            stream_mode="messages",
        ):
            if metadata.get("langgraph_node") != "chat_node":
                continue
            text = message_chunk.text
            if text:
                yield text

    return StreamingResponse(token_generator(), media_type="text/plain")
