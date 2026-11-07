"""Build a tiny in-memory PDF with pypdf to exercise the actual PDF path."""
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
from campus_assistant.documents import pdf_source, build_index
from campus_assistant.retrieval import search_docs
from campus_assistant.schemas import Search


def test_actual_pdf_page_extraction_and_index(db, tmp_path):
    writer = PdfWriter()
    for text in ("Fictional campus handbook", "Library loans last 21 days"):
        page = writer.add_blank_page(width=612, height=792)
        font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")})
        page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
        stream = DecodedStreamObject()
        stream.set_data(f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode())
        page[NameObject("/Contents")] = writer._add_object(stream)
    path = tmp_path / "trusted-handbook.pdf"
    with path.open("wb") as file:
        writer.write(file)
    source = pdf_source(path, "Test handbook", "fixture://pdf-handbook")
    assert "21 days" in source["pages"][1]
    build_index(db, [source])
    found = search_docs(db, Search(query="library loans"))["excerpts"][0]
    assert found["page"] == 2 and found["url"] == "fixture://pdf-handbook"
