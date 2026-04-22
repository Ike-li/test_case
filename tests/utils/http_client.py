from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any

import requests


@dataclass
class ResponseResult:
    response: requests.Response
    elapsed_ms: int
    assertion_context: dict[str, Any]


def _resolve_template(value: Any, env_config: dict[str, str]) -> Any:
    if isinstance(value, str):
        resolved = value
        for key, env_value in env_config.items():
            resolved = resolved.replace(f"{{{{{key}}}}}", env_value)
        return resolved
    if isinstance(value, dict):
        return {key: _resolve_template(item, env_config) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve_template(item, env_config) for item in value]
    return value


def execute_case(
    session: requests.Session,
    env_config: dict[str, str],
    case: dict[str, Any],
    body_templates: dict[str, dict[str, Any]],
) -> ResponseResult:
    session_state: dict[str, Any] = {}
    for index, setup_request in enumerate(case.get("session_setup_requests", []), start=1):
        _send_request(
            session,
            env_config,
            session_state,
            setup_request,
            body_templates,
            context=f"{case['case_id']} setup[{index}]",
        )

    started = perf_counter()
    response = _send_request(
        session,
        env_config,
        session_state,
        case,
        body_templates,
        context=case["case_id"],
    )
    elapsed_ms = int((perf_counter() - started) * 1000)
    assertion_context = dict(env_config)
    assertion_context.update(session_state)
    return ResponseResult(response=response, elapsed_ms=elapsed_ms, assertion_context=assertion_context)


def _send_request(
    session: requests.Session,
    env_config: dict[str, str],
    session_state: dict[str, Any],
    request_data: dict[str, Any],
    body_templates: dict[str, dict[str, Any]],
    *,
    context: str,
) -> requests.Response:
    template_values = dict(env_config)
    template_values.update(session_state)

    url = _resolve_template(request_data["url"], template_values)
    headers = _resolve_template(request_data.get("headers") or {}, template_values)

    auth = None
    if request_data.get("auth_type") == "basic":
        auth_payload = _resolve_template(request_data.get("auth_payload") or {}, template_values)
        auth = (auth_payload["username"], auth_payload["password"])

    json_body = None
    if request_data.get("body_ref"):
        json_body = _resolve_template(body_templates[request_data["body_ref"]], template_values)

    response = session.request(
        method=request_data["method"],
        url=url,
        headers=headers,
        json=json_body,
        auth=auth,
        timeout=request_data.get("timeout", 10),
        allow_redirects=request_data.get("follow_redirects", True),
    )
    if request_data.get("extract_fields") and response.status_code >= 400:
        raise AssertionError(
            f"{context} 前置请求失败: {request_data['method']} {url} 返回 {response.status_code}, "
            f"响应体 {response.text[:200]!r}"
        )
    _extract_fields(response, session_state, request_data.get("extract_fields") or [], context=context)
    return response


def _extract_fields(
    response: requests.Response,
    session_state: dict[str, Any],
    extract_fields: list[dict[str, str]],
    *,
    context: str = "request",
) -> None:
    if not extract_fields:
        return

    try:
        data = response.json()
    except ValueError as exc:
        raise AssertionError(f"{context} 提取字段失败: 响应不是合法 JSON，响应体 {response.text[:200]!r}") from exc
    for field in extract_fields:
        try:
            session_state[field["state_key"]] = _read_path(data, field["path"])
        except (KeyError, IndexError, ValueError, TypeError) as exc:
            raise AssertionError(
                f"{context} 提取字段失败: 路径 {field['path']} 不存在，无法写入 {field['state_key']}"
            ) from exc


def _read_path(data: Any, path: str) -> Any:
    current = data
    for part in path.split("."):
        if isinstance(current, list):
            current = current[int(part)]
            continue
        current = current[part]
    return current
