from app.modules.documents.ingestion import pdf_extractor


def test_extract_text_from_pdf_uses_ocr_when_text_layer_is_empty(tmp_path, monkeypatch):
    pdf_path = tmp_path / "scanned.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\nstream\nnot-deflated\nendstream\n%%EOF")

    expected_text = "OCR extracted policy wording from scanned document."

    monkeypatch.setattr(pdf_extractor, "_extract_via_pdfminer", lambda *_args, **_kwargs: "")
    monkeypatch.setattr(pdf_extractor, "_extract_via_deflate", lambda *_args, **_kwargs: "")
    monkeypatch.setattr(pdf_extractor, "_extract_raw_bt_et", lambda *_args, **_kwargs: "")
    monkeypatch.setattr(pdf_extractor, "_extract_via_ocr", lambda *_args, **_kwargs: expected_text)

    assert pdf_extractor.extract_text_from_pdf(pdf_path) == expected_text
