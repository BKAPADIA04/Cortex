from rag import store


def test_add_document_returns_summary(tmp_path, rag_env):
    path = tmp_path / "notes.txt"
    path.write_text("Cortex ships tool calling, streaming, and now document retrieval.")

    result = store.add_document(path, "notes.txt")

    assert result["filename"] == "notes.txt"
    assert result["chunks"] >= 1
    assert result["pages"] is None
    assert result["doc_id"]


def test_retrieve_returns_source_and_page_metadata(tmp_path, rag_env):
    path = tmp_path / "handbook.txt"
    path.write_text("The onboarding handbook explains how to request time off.")
    store.add_document(path, "handbook.txt")

    results = store.get_retriever().retrieve("time off policy", k=3)

    assert len(results) >= 1
    assert results[0]["source"] == "handbook.txt"
    assert "onboarding" in results[0]["text"]


def test_document_name_filter_scopes_retrieval(tmp_path, rag_env):
    a = tmp_path / "a.txt"
    a.write_text("Document A covers the pricing model.")
    b = tmp_path / "b.txt"
    b.write_text("Document B covers the refund policy.")
    store.add_document(a, "a.txt")
    store.add_document(b, "b.txt")

    results = store.get_retriever().retrieve("policy", k=5, document_name="b.txt")

    assert results
    assert all(r["source"] == "b.txt" for r in results)


def test_list_documents_aggregates_chunks(tmp_path, rag_env):
    path = tmp_path / "notes.txt"
    path.write_text("A short note about Cortex.")
    added = store.add_document(path, "notes.txt")

    docs = store.list_documents()

    assert len(docs) == 1
    assert docs[0]["doc_id"] == added["doc_id"]
    assert docs[0]["chunks"] == added["chunks"]


def test_delete_document_removes_all_chunks(tmp_path, rag_env):
    path = tmp_path / "notes.txt"
    path.write_text("A note that will be deleted.")
    added = store.add_document(path, "notes.txt")

    assert store.delete_document(added["doc_id"]) is True
    assert store.list_documents() == []
    assert store.delete_document(added["doc_id"]) is False


def test_retrieve_with_no_documents_returns_empty(rag_env):
    assert store.get_retriever().retrieve("anything") == []
