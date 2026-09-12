import os

from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Annotated
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph.message import add_messages
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]

llm = ChatGoogleGenerativeAI(model = 'gemini-3.6-flash')

class ChatbotState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    
def chat_node(state: ChatbotState):
    messages = state['messages']
    response = llm.invoke(messages)
    return {'messages': [response]}


graph = StateGraph(ChatbotState)
graph.add_node('chat_node', chat_node)
graph.add_edge(START, "chat_node")
graph.add_edge("chat_node", END)

pool = ConnectionPool(
    conninfo=DATABASE_URL,
    kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
)
checkpointer = PostgresSaver(pool)
checkpointer.setup()

cortex_chatbot = graph.compile(checkpointer=checkpointer)