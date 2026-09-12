from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Annotated
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph.message import add_messages

load_dotenv()

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

checkpointer = InMemorySaver()

cortex_chatbot = graph.compile(checkpointer=checkpointer)