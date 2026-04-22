from __future__ import annotations

import re
from typing import Any

import requests


def _load_json(response: requests.Response) -> Any:
    try:
        return response.json()
    except ValueError as exc:
        raise AssertionError(f"响应不是合法 JSON: {response.text[:200]}") from exc


def _read_path(data: Any, path: str) -> Any:
    current = data
    for part in path.split("."):
        if isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError) as exc:
                raise AssertionError(f"数组路径不存在: {path}") from exc
            continue
        if isinstance(current, dict) and part in current:
            current = current[part]
            continue
        raise AssertionError(f"字段路径不存在: {path}")
    return current


def assert_status_code(response: requests.Response, expected_status: int) -> None:
    assert response.status_code == expected_status, (
        f"状态码断言失败，预期 {expected_status}，实际 {response.status_code}"
    )


def assert_json_field(response: requests.Response, path: str, expected: Any) -> None:
    data = _load_json(response)
    actual = _read_path(data, path)
    assert actual == expected, f"字段断言失败，路径 {path} 预期 {expected!r}，实际 {actual!r}"


def assert_json_field_not_equal(response: requests.Response, path: str, unexpected: Any) -> None:
    data = _load_json(response)
    actual = _read_path(data, path)
    assert actual != unexpected, f"字段断言失败，路径 {path} 不应为 {unexpected!r}"


def assert_json_field_pattern(response: requests.Response, path: str, pattern: str) -> None:
    data = _load_json(response)
    actual = _read_path(data, path)
    assert isinstance(actual, str), f"字段正则断言失败，路径 {path} 不是字符串，实际 {type(actual).__name__}"
    assert re.match(pattern, actual), f"字段正则断言失败，路径 {path} 值 {actual!r} 不匹配 {pattern!r}"


def assert_structure_contains(response: requests.Response, path: str) -> None:
    data = _load_json(response)
    _read_path(data, path)


def assert_response_time(elapsed_ms: int, min_ms: int | None = None, max_ms: int | None = None) -> None:
    if min_ms is not None:
        assert elapsed_ms >= min_ms, f"响应时间断言失败，预期 >= {min_ms}ms，实际 {elapsed_ms}ms"
    if max_ms is not None:
        assert elapsed_ms < max_ms, f"响应时间断言失败，预期 < {max_ms}ms，实际 {elapsed_ms}ms"


def assert_list_min_length(response: requests.Response, min_length: int, path: str | None = None) -> None:
    data = _load_json(response)
    if path:
        data = _read_path(data, path)
    assert isinstance(data, list), f"响应结构断言失败，预期 list，实际 {type(data).__name__}"
    assert len(data) >= min_length, f"列表长度断言失败，预期 >= {min_length}，实际 {len(data)}"


def assert_empty_json_object(response: requests.Response) -> None:
    data = _load_json(response)
    assert data == {}, f"空对象断言失败，预期 {{}}，实际 {data!r}"


def assert_empty_body(response: requests.Response) -> None:
    assert response.text == "", f"空响应体断言失败，实际内容 {response.text!r}"


def assert_response_header(response: requests.Response, name: str, expected: str, mode: str = "equals") -> None:
    actual = response.headers.get(name)
    assert actual is not None, f"响应头断言失败，未找到响应头 {name}"
    if mode == "equals":
        assert actual == expected, f"响应头断言失败，{name} 预期 {expected!r}，实际 {actual!r}"
        return
    if mode == "contains":
        assert expected in actual, f"响应头断言失败，{name} 预期包含 {expected!r}，实际 {actual!r}"
        return
    raise AssertionError(f"未知响应头断言模式: {mode}")


def assert_content_type(response: requests.Response, expected: str) -> None:
    actual = response.headers.get("Content-Type", "")
    assert expected in actual, f"Content-Type 断言失败，预期包含 {expected!r}，实际 {actual!r}"


def assert_raw_text(response: requests.Response, expected: str, mode: str = "contains") -> None:
    actual = response.text
    if mode == "contains":
        assert expected in actual, f"文本断言失败，预期包含 {expected!r}，实际 {actual[:200]!r}"
        return
    if mode == "contains_casefold":
        assert expected.casefold() in actual.casefold(), (
            f"文本断言失败，预期忽略大小写包含 {expected!r}，实际 {actual[:200]!r}"
        )
        return
    if mode == "equals":
        assert actual == expected, f"文本断言失败，预期 {expected!r}，实际 {actual!r}"
        return
    raise AssertionError(f"未知文本断言模式: {mode}")
