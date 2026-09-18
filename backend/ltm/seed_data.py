"""Prefilled long-term memory. Edit this list, then run `python -m ltm.seed`
to (re)embed and load it — the chatbot never writes to the LTM store itself,
so this file is the only source of truth for what it "remembers" long-term.

Each entry is scoped to a user_id (see ltm.config.DEFAULT_USER_ID for the
single-user default) and tagged with a category:
  - "profile"     stable facts about the user (name, role, preferences)
  - "setting"     structured key-value-style facts, phrased as one fact
                   per line so they embed and match well, e.g. "favorite
                   programming language: Python"
  - "note"        prefilled facts learned from prior sessions (seeded here
                   rather than written live by the bot)
"""

from .config import DEFAULT_USER_ID

SEED_MEMORIES: list[dict] = [
    {
        "user_id": DEFAULT_USER_ID,
        "category": "profile",
        "content": "The user's name is Bhavya. They are the developer building and maintaining Cortex.",
    },
    {
        "user_id": DEFAULT_USER_ID,
        "category": "profile",
        "content": "The user prefers concise, direct answers over long explanations.",
    },
    {
        "user_id": DEFAULT_USER_ID,
        "category": "setting",
        "content": "preferred programming language: Python",
    },
    {
        "user_id": DEFAULT_USER_ID,
        "category": "setting",
        "content": "timezone: Asia/Kolkata",
    },
    {
        "user_id": DEFAULT_USER_ID,
        "category": "note",
        "content": "The user is building Cortex, a chatbot with RAG over uploaded documents, web search, and human-in-the-loop tool approval.",
    },
]
