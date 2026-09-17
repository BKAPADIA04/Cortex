import docx
import pytest
from pypdf import PdfWriter

from rag.errors import DocumentParsingError, EmptyDocumentError, UnsupportedFileTypeError
from rag.loaders import parse_file


def test_parse_txt(tmp_path):
    path = tmp_path / "notes.txt"
    path.write_text("Cortex is a stateful chatbot.")

    docs = parse_file(path, "notes.txt")

    assert len(docs) == 1
    assert "Cortex" in docs[0].page_content
    assert docs[0].metadata.get("page") is None


def test_parse_empty_txt_raises(tmp_path):
    path = tmp_path / "empty.txt"
    path.write_text("   \n  ")

    with pytest.raises(EmptyDocumentError):
        parse_file(path, "empty.txt")


def test_parse_unsupported_extension_raises(tmp_path):
    path = tmp_path / "data.csv"
    path.write_text("a,b\n1,2")

    with pytest.raises(UnsupportedFileTypeError):
        parse_file(path, "data.csv")


def test_parse_docx(tmp_path):
    path = tmp_path / "report.docx"
    document = docx.Document()
    document.add_paragraph("Quarterly results look strong.")
    document.save(str(path))

    docs = parse_file(path, "report.docx")

    assert len(docs) == 1
    assert "Quarterly results" in docs[0].page_content


def test_parse_blank_pdf_raises_empty_document(tmp_path):
    path = tmp_path / "blank.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    with open(path, "wb") as f:
        writer.write(f)

    with pytest.raises(EmptyDocumentError):
        parse_file(path, "blank.pdf")


def test_parse_missing_pdf_raises_parsing_error(tmp_path):
    path = tmp_path / "not_a_pdf.pdf"
    path.write_bytes(b"this is not a real pdf")

    with pytest.raises(DocumentParsingError):
        parse_file(path, "not_a_pdf.pdf")
