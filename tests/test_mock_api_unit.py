from fastapi.testclient import TestClient

from tests.mock_api.app import create_app


client = TestClient(create_app())


def test_mock_health_ok():
    response = client.get("/_health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "test_case_mock_api"
    assert response.json()["version"] == "1"
    assert response.json()["config_signature"]


def test_mock_httpbin_redirect_location_matches_contract():
    response = client.get("/redirect-to?url=%2Fget%3Ffrom%3Dredirect", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "/get?from=redirect"


def test_mock_jsonplaceholder_nested_posts_route():
    response = client.get("/jsonplaceholder/users/1/posts")
    data = response.json()

    assert response.status_code == 200
    assert isinstance(data, list)
    assert data[0]["userId"] == 1


def test_mock_dummyjson_login_and_me_flow():
    login = client.post(
        "/dummyjson/auth/login",
        json={"username": "emilys", "password": "emilyspass", "expiresInMins": 30},
    )
    token = login.json()["accessToken"]
    me = client.get("/dummyjson/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert login.status_code == 200
    assert me.status_code == 200
    assert me.json()["username"] == "emilys"


def test_mock_dummyjson_login_respects_configured_credentials(monkeypatch):
    monkeypatch.setenv("DUMMYJSON_USERNAME", "local-user")
    monkeypatch.setenv("DUMMYJSON_PASSWORD", "local-pass")
    local_client = TestClient(create_app())

    wrong_login = local_client.post(
        "/dummyjson/auth/login",
        json={"username": "emilys", "password": "emilyspass", "expiresInMins": 30},
    )
    login = local_client.post(
        "/dummyjson/auth/login",
        json={"username": "local-user", "password": "local-pass", "expiresInMins": 30},
    )
    token = login.json()["accessToken"]
    me = local_client.get("/dummyjson/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert wrong_login.status_code == 400
    assert login.status_code == 200
    assert login.json()["username"] == "local-user"
    assert me.status_code == 200
    assert me.json()["username"] == "local-user"


def test_mock_dummyjson_user_resource_matches_configured_auth_user(monkeypatch):
    monkeypatch.setenv("DUMMYJSON_USERNAME", "local-user")
    monkeypatch.setenv("DUMMYJSON_PASSWORD", "local-pass")
    local_client = TestClient(create_app())

    response = local_client.get("/dummyjson/users/1")

    assert response.status_code == 200
    assert response.json()["username"] == "local-user"
    assert response.json()["email"] == "local-user@x.dummyjson.com"


def test_mock_missing_resource_returns_404():
    response = client.get("/dummyjson/users/999")

    assert response.status_code == 404
