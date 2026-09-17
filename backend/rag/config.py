import os
from pathlib import Path

# All RAG state (uploaded originals + the Chroma index) lives under this
# directory so it can be wiped or backed up as one unit. Override via env
# var if it should live outside the repo (e.g. in production).
RAG_DATA_DIR = Path(os.environ.get("RAG_DATA_DIR", Path(__file__).resolve().parent.parent / "rag_data"))
UPLOAD_DIR = RAG_DATA_DIR / "uploads"
CHROMA_PERSIST_DIR = str(RAG_DATA_DIR / "chroma")
COLLECTION_NAME = "cortex_documents"

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}
MAX_FILE_SIZE_BYTES = int(os.environ.get("RAG_MAX_FILE_SIZE_MB", "20")) * 1024 * 1024

CHUNK_SIZE = int(os.environ.get("RAG_CHUNK_SIZE", "1000"))
CHUNK_OVERLAP = int(os.environ.get("RAG_CHUNK_OVERLAP", "150"))
RETRIEVAL_K = int(os.environ.get("RAG_RETRIEVAL_K", "4"))

# Reuses GOOGLE_API_KEY — no separate credential needed for embeddings.
EMBEDDING_MODEL = os.environ.get("RAG_EMBEDDING_MODEL", "models/gemini-embedding-001")
