"""Vector store: embed, persist, list, delete, and retrieve document chunks.

Chroma is used as the local/simple vector store (persisted to disk under
`rag_data/chroma`, no external service required). Retrieval is exposed
through the `Retriever` interface below rather than called directly, so a
later hybrid (BM25 + vector) or reranking retriever can be swapped in via
`get_retriever()` without touching callers (the MCP tool, upload endpoint).
"""

import time
import uuid
from pathlib import Path
from typing import Protocol, TypedDict

from langchain_chroma import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from . import config
from .errors import EmbeddingError
from .loaders import parse_file

config.RAG_DATA_DIR.mkdir(parents=True, exist_ok=True)
config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

_embeddings: GoogleGenerativeAIEmbeddings | None = None
_vector_store: Chroma | None = None


def get_embeddings() -> GoogleGenerativeAIEmbeddings:
    global _embeddings
    if _embeddings is None:
        _embeddings = GoogleGenerativeAIEmbeddings(model=config.EMBEDDING_MODEL)
    return _embeddings


def get_vector_store() -> Chroma:
    global _vector_store
    if _vector_store is None:
        _vector_store = Chroma(
            collection_name=config.COLLECTION_NAME,
            embedding_function=get_embeddings(),
            persist_directory=config.CHROMA_PERSIST_DIR,
        )
    return _vector_store


class UploadResult(TypedDict):
    doc_id: str
    filename: str
    chunks: int
    pages: int | None


def add_document(file_path: Path, filename: str) -> UploadResult:
    """Parse, chunk, embed, and store a single uploaded file.

    Raises UnsupportedFileTypeError / DocumentParsingError /
    EmptyDocumentError (from parsing) or EmbeddingError (from the vector
    store write) — the upload endpoint maps these to 4xx/5xx responses.
    """
    docs = parse_file(file_path, filename)
    pages = max((d.metadata.get("page", 0) for d in docs), default=0) or None

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.CHUNK_SIZE, chunk_overlap=config.CHUNK_OVERLAP
    )
    chunks = splitter.split_documents(docs)
    if not chunks:
        chunks = docs

    doc_id = uuid.uuid4().hex
    uploaded_at = time.time()
    for chunk in chunks:
        chunk.metadata.update(
            {
                "doc_id": doc_id,
                "source": filename,
                "uploaded_at": uploaded_at,
            }
        )
        chunk.metadata.setdefault("page", None)

    ids = [f"{doc_id}-{i}" for i in range(len(chunks))]

    try:
        get_vector_store().add_documents(chunks, ids=ids)
    except Exception as exc:
        raise EmbeddingError(f"Failed to embed '{filename}': {exc}") from exc

    return {"doc_id": doc_id, "filename": filename, "chunks": len(chunks), "pages": pages}


class DocumentSummary(TypedDict):
    doc_id: str
    filename: str
    chunks: int
    uploaded_at: float


def list_documents() -> list[DocumentSummary]:
    """Aggregate stored chunk metadata back into one row per uploaded file."""
    raw = get_vector_store().get(include=["metadatas"])
    by_doc: dict[str, DocumentSummary] = {}
    for metadata in raw.get("metadatas") or []:
        doc_id = metadata.get("doc_id")
        if not doc_id:
            continue
        entry = by_doc.setdefault(
            doc_id,
            {
                "doc_id": doc_id,
                "filename": metadata.get("source", "unknown"),
                "chunks": 0,
                "uploaded_at": metadata.get("uploaded_at", 0),
            },
        )
        entry["chunks"] += 1
    return sorted(by_doc.values(), key=lambda d: d["uploaded_at"], reverse=True)


def delete_document(doc_id: str) -> bool:
    """Delete every chunk belonging to a document. Returns False if unknown."""
    store = get_vector_store()
    existing = store.get(where={"doc_id": doc_id}, include=[])
    if not existing.get("ids"):
        return False
    store.delete(ids=existing["ids"])
    return True


class RetrievedChunk(TypedDict):
    text: str
    source: str
    page: int | None
    doc_id: str
    score: float  # raw distance — lower is more similar


class Retriever(Protocol):
    def retrieve(
        self, query: str, k: int = config.RETRIEVAL_K, document_name: str | None = None
    ) -> list[RetrievedChunk]: ...


class VectorStoreRetriever:
    """Plain similarity-search retriever over the Chroma store.

    Swap this out (or wrap it) behind `get_retriever()` to add hybrid
    keyword+vector search, reranking, or a Graph RAG traversal later —
    everything downstream only depends on the `Retriever` protocol.
    """

    def retrieve(
        self, query: str, k: int = config.RETRIEVAL_K, document_name: str | None = None
    ) -> list[RetrievedChunk]:
        store = get_vector_store()
        where = {"source": document_name} if document_name else None
        # Raw distance (lower = more similar), not a normalized relevance
        # score — Chroma's relevance normalization assumes a distance metric
        # that isn't guaranteed here across embedding providers.
        results = store.similarity_search_with_score(query, k=k, filter=where)
        return [
            {
                "text": doc.page_content,
                "source": doc.metadata.get("source", "unknown"),
                "page": doc.metadata.get("page"),
                "doc_id": doc.metadata.get("doc_id", ""),
                "score": score,
            }
            for doc, score in results
        ]


def get_retriever() -> Retriever:
    return VectorStoreRetriever()
