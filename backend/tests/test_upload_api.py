import pytest
from fastapi.testclient import TestClient


class _DummyPool:
    async def close(self):
        pass


class _DummyGraph:
    async def ainvoke(self, *args, **kwargs):
        return {"messages": []}


@pytest.fixture
def client(monkeypatch, rag_env):
    import chatbot
    import server

    async def fake_build_chatbot():
        return _DummyGraph(), _DummyPool()

    monkeypatch.setattr(chatbot, "build_chatbot", fake_build_chatbot)
    with TestClient(server.app) as c:
        yield c


def test_upload_rejects_unsupported_extension(client):
    resp = client.post("/documents", files={"file": ("notes.csv", b"a,b\n1,2", "text/csv")})
    assert resp.status_code == 400


def test_upload_rejects_empty_file(client):
    resp = client.post("/documents", files={"file": ("empty.txt", b"", "text/plain")})
    assert resp.status_code == 400


def test_upload_txt_then_list_then_delete(client):
    resp = client.post(
        "/documents", files={"file": ("notes.txt", b"Cortex is a stateful chatbot.", "text/plain")}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["filename"] == "notes.txt"
    assert body["chunks"] >= 1
    doc_id = body["doc_id"]

    listed = client.get("/documents").json()
    assert any(d["doc_id"] == doc_id for d in listed)

    deleted = client.delete(f"/documents/{doc_id}")
    assert deleted.status_code == 200

    listed_after = client.get("/documents").json()
    assert not any(d["doc_id"] == doc_id for d in listed_after)


def test_delete_unknown_document_returns_404(client):
    resp = client.delete("/documents/does-not-exist")
    assert resp.status_code == 404
