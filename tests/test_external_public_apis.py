import pytest

from tests.data.external_api_cases import BODY_TEMPLATES, EXTERNAL_API_CASES
from tests.utils.assertions import (
    assert_content_type,
    assert_empty_body,
    assert_empty_json_object,
    assert_json_field,
    assert_json_field_not_equal,
    assert_json_field_pattern,
    assert_list_min_length,
    assert_raw_text,
    assert_response_header,
    assert_response_time,
    assert_status_code,
    assert_structure_contains,
)
from tests.utils.http_client import execute_case
from tests.utils.http_client import _resolve_template


@pytest.mark.external_api
@pytest.mark.parametrize(
    "case",
    EXTERNAL_API_CASES,
    ids=[f"{case['case_id']}-{case['case_name']}" for case in EXTERNAL_API_CASES],
)
def test_external_public_api_cases(http_session, env_config, case):
    result = execute_case(http_session, env_config, case, BODY_TEMPLATES)
    response = result.response
    assertion_context = result.assertion_context

    assert_status_code(response, case["expected_status"])

    list_assert = case.get("list_assert")
    if list_assert:
        assert_list_min_length(response, list_assert["min_length"], list_assert.get("path"))

    for field_assert in case.get("field_asserts", []):
        expected = _resolve_template(field_assert["expected"], assertion_context)
        assert_json_field(response, field_assert["path"], expected)

    for field_not_equals_assert in case.get("field_not_equals_asserts", []):
        unexpected = _resolve_template(field_not_equals_assert["unexpected"], assertion_context)
        assert_json_field_not_equal(response, field_not_equals_assert["path"], unexpected)

    for field_pattern_assert in case.get("field_pattern_asserts", []):
        assert_json_field_pattern(response, field_pattern_assert["path"], field_pattern_assert["pattern"])

    for structure_assert in case.get("structure_asserts", []):
        assert_structure_contains(response, structure_assert["path"])

    for header_assert in case.get("header_asserts", []):
        expected = _resolve_template(header_assert["expected"], assertion_context)
        assert_response_header(response, header_assert["name"], expected, header_assert.get("mode", "equals"))

    if case.get("content_type_assert"):
        assert_content_type(response, case["content_type_assert"])

    for raw_text_assert in case.get("raw_text_asserts", []):
        assert_raw_text(response, raw_text_assert["expected"], raw_text_assert.get("mode", "contains"))

    if case.get("empty_json_object"):
        assert_empty_json_object(response)

    if case.get("empty_body"):
        assert_empty_body(response)

    assert_response_time(result.elapsed_ms, **case["response_time_assert"])
