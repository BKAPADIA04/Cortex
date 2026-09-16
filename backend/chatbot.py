import os

from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Annotated
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from tools import TOOLS

load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]

llm = ChatGoogleGenerativeAI(model = 'gemini-3.6-flash')
llm_with_tools = llm.bind_tools(TOOLS)

class ChatbotState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]

def chat_node(state: ChatbotState):
    messages = state['messages']
    response = llm_with_tools.invoke(messages)
    return {'messages': [response]}


graph = StateGraph(ChatbotState)
graph.add_node('chat_node', chat_node)
graph.add_node('tools', ToolNode(TOOLS))
graph.add_edge(START, "chat_node")
graph.add_conditional_edges("chat_node", tools_condition, {"tools": "tools", END: END})
graph.add_edge("tools", "chat_node")

pool = ConnectionPool(
    conninfo=DATABASE_URL,
    kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
)
checkpointer = PostgresSaver(pool)
checkpointer.setup()

cortex_chatbot = graph.compile(checkpointer=checkpointer)