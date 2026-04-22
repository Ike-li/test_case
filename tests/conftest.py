import os
import hashlib
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest
import requests

from tests.data.external_api_cases import ENV_DEFAULTS

MOCK_API_HOST = "127.0.0.1"
MOCK_API_PORT = "18080"
MOCK_API_ROOT = f"http://{MOCK_API_HOST}:{MOCK_API_PORT}"
MOCK_API_HEALTH_URL = f"{MOCK_API_ROOT}/_health"
MOCK_API_SERVICE_NAME = "test_case_mock_api"


def _read_env(name: str) -> str:
    value = os.getenv(name.upper())
    if value is None or not value.strip():
        return ENV_DEFAULTS[name]
    return value.strip()


def _has_external_api_tests(session: pytest.Session) -> bool:
    return any(item.get_closest_marker("external_api") for item in session.items)


def _mock_api_health_payload() -> dict[str, str] | None:
    try:
        with urllib.request.urlopen(MOCK_API_HEALTH_URL, timeout=0.2) as response:
            if response.status != 200:
                return None
            import json

            payload = json.loads(response.read().decode("utf-8"))
            if payload.get("service") != MOCK_API_SERVICE_NAME:
                return None
            return payload
    except (urllib.error.URLError, ValueError, TimeoutError):
        return None


def _mock_api_is_healthy() -> bool:
    return _mock_api_health_payload() is not None


def _expected_mock_api_config_signature() -> str:
    username = os.getenv("DUMMYJSON_USERNAME", "emilys")
    password = os.getenv("DUMMYJSON_PASSWORD", "emilyspass")
    payload = f"dummyjson:{username}:{password}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


def _mock_api_matches_expected_config() -> bool:
    payload = _mock_api_health_payload()
    if payload is None:
        return False
    return payload.get("config_signature") == _expected_mock_api_config_signature()


def _port_is_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        return sock.connect_ex((host, port)) == 0


def _wait_for_mock_api(timeout_seconds: float = 10.0) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if _mock_api_matches_expected_config():
            return True
        time.sleep(0.2)
    return False


def _apply_default_mock_env() -> None:
    os.environ.setdefault("BASE_URL", MOCK_API_ROOT)
    os.environ.setdefault("JSONPLACEHOLDER_BASE_URL", f"{MOCK_API_ROOT}/jsonplaceholder")
    os.environ.setdefault("DUMMYJSON_BASE_URL", f"{MOCK_API_ROOT}/dummyjson")
    os.environ.setdefault("DUMMYJSON_USERNAME", "emilys")
    os.environ.setdefault("DUMMYJSON_PASSWORD", "emilyspass")


@pytest.fixture(scope="session", autouse=True)
def local_mock_api_server(request: pytest.FixtureRequest):
    if not _has_external_api_tests(request.session):
        yield
        return

    if os.getenv("TEST_CASE_DISABLE_AUTO_MOCK_API") == "1":
        yield
        return

    _apply_default_mock_env()

    if _mock_api_matches_expected_config():
        yield
        return

    existing_payload = _mock_api_health_payload()
    if existing_payload is not None:
        raise RuntimeError(
            "existing mock api service is running with a different configuration; "
            "stop it first or align DUMMYJSON_USERNAME/DUMMYJSON_PASSWORD"
        )

    if _port_is_open(MOCK_API_HOST, int(MOCK_API_PORT)):
        raise RuntimeError(
            f"port {MOCK_API_PORT} is already in use by a non-{MOCK_API_SERVICE_NAME} service"
        )

    root_dir = Path(__file__).resolve().parents[1]
    log_file = root_dir / ".mock_api.auto.log"
    with log_file.open("w", encoding="utf-8") as log_fp:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "tests.mock_api.app:app",
                "--host",
                MOCK_API_HOST,
                "--port",
                MOCK_API_PORT,
            ],
            cwd=root_dir,
            stdout=log_fp,
            stderr=subprocess.STDOUT,
        )

    try:
        if not _wait_for_mock_api():
            raise RuntimeError(f"mock api failed to start, see {log_file}")
        yield
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


@pytest.fixture(scope="session")
def env_config() -> dict[str, str]:
    return {
        "base_url": _read_env("base_url"),
        "jsonplaceholder_base_url": _read_env("jsonplaceholder_base_url"),
        "username": _read_env("username"),
        "password": _read_env("password"),
        "dummyjson_base_url": _read_env("dummyjson_base_url"),
        "dummyjson_username": _read_env("dummyjson_username"),
        "dummyjson_password": _read_env("dummyjson_password"),
    }


@pytest.fixture(scope="function")
def http_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": "pytest-external-api-suite/1.0"})
    yield session
    session.close()
