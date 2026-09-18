import os

TABLE_NAME = "ltm_memories"

# Reuses GOOGLE_API_KEY, same embedding model as the RAG store — no separate
# credential or extra model needed.
EMBEDDING_MODEL = os.environ.get("LTM_EMBEDDING_MODEL", "models/gemini-embedding-001")

# Default scope for requests that don't specify a user (single-user setups,
# local dev). Real multi-user deployments should always pass a user_id.
DEFAULT_USER_ID = "default"

RETRIEVAL_K = int(os.environ.get("LTM_RETRIEVAL_K", "5"))

# Cosine-distance threshold (0 = identical, higher = less similar) below
# which save_memory updates an existing row instead of inserting a new one.
# Tune down if unrelated facts are getting merged, up if near-duplicates keep
# piling up.
DEDUPE_THRESHOLD = float(os.environ.get("LTM_DEDUPE_THRESHOLD", "0.28"))
