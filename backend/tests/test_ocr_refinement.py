from app.services.documents.ocr_refinement import OcrRefinementService


def test_parse_json_accepts_valid_payload():
    service = OcrRefinementService()
    payload = '{"cleaned_text":"ok","entities":{"medications":["aspirin"]}}'
    parsed = service._parse_json(payload)
    assert parsed["cleaned_text"] == "ok"
    assert parsed["entities"]["medications"] == ["aspirin"]


def test_parse_json_extracts_embedded_payload():
    service = OcrRefinementService()
    payload = "Result:\n```json\n{\"cleaned_text\":\"ok\",\"entities\":{}}\n```\n"
    parsed = service._parse_json(payload)
    assert parsed["cleaned_text"] == "ok"
    assert parsed["entities"] == {}
