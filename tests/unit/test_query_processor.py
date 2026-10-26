"""Unit tests kiểm tra module xử lý câu hỏi (Query Processor)."""

import pytest
from haui_rag.core.query_processor import classify_query, expand_query, extract_entities


def test_classify_query_types():
    assert classify_query("Điều kiện tốt nghiệp là gì?") == "factual"
    assert classify_query("Quy trình xin bảo lưu kết quả học tập?") == "procedural"
    assert classify_query("So sánh chương trình thạc sĩ chính quy và vừa làm vừa học?") == "comparative"
    assert classify_query("Thời tiết ngày mai thế nào?") == "out_of_scope"


def test_expand_query_synonyms():
    expanded = expand_query("Điều kiện tốt nghiệp thạc sĩ")
    assert isinstance(expanded, list)
    assert len(expanded) >= 1
    assert "Điều kiện tốt nghiệp thạc sĩ" in expanded


def test_expand_query_student_responsibilities():
    query = "Nhiệm vụ và trách nhiệm của sinh viên"
    expanded = expand_query(query)

    assert expanded[0] == query
    assert len(expanded) <= 3
    assert any("nghĩa vụ của sinh viên" in item.lower() for item in expanded)
    assert any("người học" in item.lower() for item in expanded)


def test_expand_query_empty_input():
    assert expand_query("   ") == []


def test_extract_entities_accuracy():
    res = extract_entities("Theo Điều 15 Quyết định 41 đào tạo thạc sĩ")
    assert res["dieu"] == "15"
    assert res["ma_van_ban"] == "41"
    assert res["bac_dao_tao"] == "thạc sĩ"
