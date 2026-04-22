import os
import requests

from tests.data.external_api_cases import BODY_TEMPLATES, EXTERNAL_API_CASES
from tests.conftest import _apply_default_mock_env, _mock_api_health_payload, _mock_api_matches_expected_config
from tests.utils.assertions import (
    assert_content_type,
    assert_json_field_not_equal,
    assert_raw_text,
    assert_response_header,
)
from tests.utils.http_client import _extract_fields, _resolve_template, execute_case


def test_external_api_case_count_is_119():
    assert len(EXTERNAL_API_CASES) == 119


def test_case_ids_are_unique():
    case_ids = [case["case_id"] for case in EXTERNAL_API_CASES]
    assert len(case_ids) == len(set(case_ids))


def test_all_body_refs_exist():
    for case in EXTERNAL_API_CASES:
        body_ref = case.get("body_ref")
        if body_ref is not None:
            assert body_ref in BODY_TEMPLATES


def test_case_schema_does_not_keep_removed_allow_non_json_flag():
    for case in EXTERNAL_API_CASES:
        assert "allow_non_json" not in case


def test_each_case_has_at_least_two_assertion_categories():
    for case in EXTERNAL_API_CASES:
        categories = {"status_code"}
        if case.get("field_asserts") or case.get("field_not_equals_asserts") or case.get("field_pattern_asserts"):
            categories.add("field")
        if case.get("structure_asserts") or case.get("list_assert") or case.get("empty_json_object"):
            categories.add("structure")
        if case.get("header_asserts"):
            categories.add("headers")
        if case.get("raw_text_asserts") or case.get("empty_body"):
            categories.add("body")
        assert len(categories) >= 2, f"{case['case_id']} 缺少足够断言类别"


def test_template_resolution_uses_env_config():
    env_config = {
        "base_url": "https://httpbin.org",
        "username": "user",
        "password": "passwd",
    }

    resolved = _resolve_template("{{base_url}}/basic-auth/{{username}}/{{password}}", env_config)

    assert resolved == "https://httpbin.org/basic-auth/user/passwd"


def test_template_resolution_supports_dummyjson_env():
    env_config = {
        "dummyjson_base_url": "https://dummyjson.com",
        "dummyjson_username": "emilys",
        "dummyjson_password": "emilyspass",
    }

    resolved = _resolve_template(
        "{{dummyjson_base_url}}/auth/login/{{dummyjson_username}}/{{dummyjson_password}}",
        env_config,
    )

    assert resolved == "https://dummyjson.com/auth/login/emilys/emilyspass"


def test_header_and_content_type_assertions_support_contains():
    response = requests.Response()
    response.status_code = 200
    response._content = b"ok"
    response.headers["Content-Type"] = "application/json; charset=utf-8"
    response.headers["Location"] = "/get?from=redirect"

    assert_content_type(response, "application/json")
    assert_response_header(response, "Location", "from=redirect", "contains")


def test_raw_text_assertion_supports_casefold_contains():
    response = requests.Response()
    response.status_code = 418
    response._content = b"I'm a TEAPOT"

    assert_raw_text(response, "teapot", "contains_casefold")


def test_extract_fields_writes_session_state():
    response = requests.Response()
    response.status_code = 200
    response._content = b'{"accessToken":"abc","refreshToken":"xyz"}'
    state = {}

    _extract_fields(
        response,
        state,
        [
            {"path": "accessToken", "state_key": "dummyjson_access_token"},
            {"path": "refreshToken", "state_key": "dummyjson_refresh_token"},
        ],
    )

    assert state == {
        "dummyjson_access_token": "abc",
        "dummyjson_refresh_token": "xyz",
    }


def test_extract_fields_raises_clear_error_for_missing_path():
    response = requests.Response()
    response.status_code = 200
    response._content = b'{"accessToken":"abc"}'

    try:
        _extract_fields(
            response,
            {},
            [{"path": "refreshToken", "state_key": "dummyjson_refresh_token"}],
            context="API-111 setup[1]",
        )
    except AssertionError as exc:
        assert "API-111 setup[1] 提取字段失败" in str(exc)
        assert "refreshToken" in str(exc)
    else:
        raise AssertionError("expected AssertionError")


def test_json_field_not_equal_assertion_supports_template_driven_comparisons():
    response = requests.Response()
    response.status_code = 200
    response._content = b'{"accessToken":"new-token","refreshToken":"new-refresh"}'

    assert_json_field_not_equal(response, "accessToken", "old-token")
    assert_json_field_not_equal(response, "refreshToken", "old-refresh")


def test_execute_case_exposes_setup_state_for_followup_assertions():
    class FakeSession:
        def __init__(self):
            self.calls = 0

        def request(self, **kwargs):
            response = requests.Response()
            response.status_code = 200
            if self.calls == 0:
                response._content = b'{"accessToken":"old-token","refreshToken":"old-refresh"}'
            else:
                response._content = b'{"accessToken":"new-token","refreshToken":"new-refresh"}'
            self.calls += 1
            return response

    case = {
        "case_id": "API-111",
        "method": "POST",
        "url": "https://example.test/auth/refresh",
        "headers": {},
        "body_ref": "BODY-019",
        "session_setup_requests": [
            {
                "method": "POST",
                "url": "https://example.test/auth/login",
                "headers": {},
                "extract_fields": [
                    {"path": "accessToken", "state_key": "dummyjson_access_token"},
                    {"path": "refreshToken", "state_key": "dummyjson_refresh_token"},
                ],
            }
        ],
    }

    result = execute_case(FakeSession(), {}, case, BODY_TEMPLATES)

    assert result.assertion_context["dummyjson_access_token"] == "old-token"
    assert result.assertion_context["dummyjson_refresh_token"] == "old-refresh"


def test_semantic_cases_have_value_assertions_for_behavior_not_just_structure():
    cases = {case["case_id"]: case for case in EXTERNAL_API_CASES}

    assert any(item["path"] == "products.0.price" for item in cases["API-068"]["field_asserts"])
    assert any(item["path"] == "users.0.hair.color" for item in cases["API-077"]["field_asserts"])
    assert any(item["path"] == "comments.0.id" for item in cases["API-094"]["field_asserts"])
    assert any(item["path"] == "accessToken" for item in cases["API-111"]["field_not_equals_asserts"])


def test_negative_resource_cases_cover_not_found_paths():
    cases = {case["case_id"]: case for case in EXTERNAL_API_CASES}

    for case_id in ("API-114", "API-115", "API-116", "API-117", "API-118", "API-119"):
        assert cases[case_id]["expected_status"] == 404
        assert any(item["path"] == "detail" for item in cases[case_id]["field_asserts"])


def test_apply_default_mock_env_does_not_override_existing_values(monkeypatch):
    monkeypatch.setenv("BASE_URL", "http://custom.local")
    monkeypatch.delenv("JSONPLACEHOLDER_BASE_URL", raising=False)
    monkeypatch.delenv("DUMMYJSON_BASE_URL", raising=False)

    _apply_default_mock_env()

    assert os.environ["BASE_URL"] == "http://custom.local"
    assert os.environ["JSONPLACEHOLDER_BASE_URL"] == "http://127.0.0.1:18080/jsonplaceholder"
    assert os.environ["DUMMYJSON_BASE_URL"] == "http://127.0.0.1:18080/dummyjson"


def test_mock_api_health_payload_rejects_non_project_service(monkeypatch):
    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'{"status":"ok","service":"not_ours"}'

    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: FakeResponse())

    assert _mock_api_health_payload() is None


def test_mock_api_matches_expected_config_rejects_stale_service(monkeypatch):
    monkeypatch.setenv("DUMMYJSON_USERNAME", "local-user")
    monkeypatch.setenv("DUMMYJSON_PASSWORD", "local-pass")

    def fake_payload():
        return {
            "status": "ok",
            "service": "test_case_mock_api",
            "version": "1",
            "config_signature": "stale-signature",
        }

    monkeypatch.setattr("tests.conftest._mock_api_health_payload", fake_payload)

    assert _mock_api_matches_expected_config() is False
