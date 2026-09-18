import os

TABLE_NAME = "ltm_memories"

# Reuses GOOGLE_API_KEY, same embedding model as the RAG store — no separate
# credential or extra model needed.
EMBEDDING_MODEL = os.environ.get("LTM_EMBEDDING_MODEL", "models/gemini-embedding-001")

# Default scope for requests that don't specify a user (single-user setups,
# local dev). Real multi-user deployments should always pass a user_id.
DEFAULT_USER_ID = "default"

RETRIEVAL_K = int(os.environ.get("LTM_RETRIEVAL_K", "5"))
