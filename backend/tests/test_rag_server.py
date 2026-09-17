from mcp_servers.rag_server import _format_results


def test_format_results_empty():
    assert _format_results([]) == "No relevant information found in the uploaded documents."


def test_format_results_includes_source_and_page():
    chunks = [
        {"text": "Revenue grew 12%.", "source": "report.pdf", "page": 3, "doc_id": "d1", "score": 0.9},
    ]

    formatted = _format_results(chunks)

    assert "report.pdf, page 3" in formatted
    assert "Revenue grew 12%." in formatted


def test_format_results_without_page():
    chunks = [
        {"text": "Refunds within 30 days.", "source": "faq.txt", "page": None, "doc_id": "d2", "score": 0.5},
    ]

    formatted = _format_results(chunks)

    assert "faq.txt\n" in formatted or formatted.endswith("faq.txt")
    assert "page" not in formatted.split("\n")[0]
