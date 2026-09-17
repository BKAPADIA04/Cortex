import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rag import store  # noqa: E402
from rag.config import RETRIEVAL_K  # noqa: E402
from rag.errors import RagError  # noqa: E402

mcp = FastMCP("cortex-rag")


def _format_results(chunks: list[store.RetrievedChunk]) -> str:
    if not chunks:
        return "No relevant information found in the uploaded documents."

    blocks = []
    for i, chunk in enumerate(chunks, start=1):
        citation = chunk["source"] + (f", page {chunk['page']}" if chunk["page"] else "")
        blocks.append(f"[{i}] Source: {citation}\n{chunk['text']}")
    return "\n\n".join(blocks)


@mcp.tool()
def retrieve_documents(query: str, document_name: str | None = None) -> str:
    """Search the user's uploaded documents (PDF/DOCX/TXT) for chunks relevant
    to the query. Use this whenever the user asks a question that could be
    answered from a document they've uploaded, or explicitly refers to "the
    document"/"the file"/an uploaded document by name.

    Each result is tagged with its source document and page number (when
    available) — always cite these in your answer, e.g. "(report.pdf, page 3)".
    If no documents have been uploaded, or nothing relevant is found, say so
    instead of guessing.

    Args:
        query: What to search for, phrased as a natural-language question.
        document_name: Optional exact filename to restrict the search to a
            single previously uploaded document.
    """
    try:
        chunks = store.get_retriever().retrieve(query, k=RETRIEVAL_K, document_name=document_name)
    except RagError as exc:
        return f"Retrieval failed: {exc}"
    except Exception as exc:
        return f"Retrieval failed unexpectedly: {exc}"

    return _format_results(chunks)


@mcp.tool()
def list_uploaded_documents() -> str:
    """List the documents the user has uploaded so far, with chunk counts.
    Use this if the user asks what documents are available or you need an
    exact filename to pass to retrieve_documents.
    """
    docs = store.list_documents()
    if not docs:
        return "No documents have been uploaded yet."
    return "\n".join(f"- {d['filename']} ({d['chunks']} chunks)" for d in docs)


if __name__ == "__main__":
    mcp.run(transport="stdio")
