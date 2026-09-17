import sys
from pathlib import Path

import pytest
from langchain_core.embeddings import Embeddings

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import rag.config as config
import rag.store as store


class FakeEmbeddings(Embeddings):
    """Deterministic, offline stand-in for GoogleGenerativeAIEmbeddings so
    tests don't need network access or GOOGLE_API_KEY."""

    def _vector(self, text: str) -> list[float]:
        h = abs(hash(text))
        return [((h >> (i * 4)) % 17) / 17 for i in range(16)]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)


@pytest.fixture
def rag_env(tmp_path, monkeypatch):
    """Point the RAG pipeline at a throwaway Chroma dir with fake embeddings."""
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(config, "CHROMA_PERSIST_DIR", str(tmp_path / "chroma"))
    monkeypatch.setattr(config, "UPLOAD_DIR", upload_dir)
    monkeypatch.setattr(store, "_vector_store", None)
    monkeypatch.setattr(store, "_embeddings", FakeEmbeddings())

    try:
        import server

        monkeypatch.setattr(server, "UPLOAD_DIR", upload_dir)
    except ModuleNotFoundError:
        pass

    yield
