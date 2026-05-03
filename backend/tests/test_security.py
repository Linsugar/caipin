from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app


def test_protected_endpoints_reject_missing_api_key(tmp_path: Path):
    app = create_app(testing=True, storage_root=tmp_path)
    client = TestClient(app)

    response = client.post(
        "/api/v1/images",
        files={"file": ("food.jpg", b"fake-image", "image/jpeg")},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "missing api key"


def test_protected_endpoints_reject_invalid_api_key(tmp_path: Path):
    app = create_app(testing=True, storage_root=tmp_path)
    client = TestClient(app)

    response = client.post(
        "/api/v1/locations/nearby",
        headers={"X-Client-Key": "wrong"},
        json={"latitude": 31.23, "longitude": 121.47},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "invalid api key"


def test_protected_endpoints_accept_valid_api_key(tmp_path: Path):
    app = create_app(testing=True, storage_root=tmp_path)
    client = TestClient(app)

    response = client.post(
        "/api/v1/images",
        headers={"X-Client-Key": "dev-client-key"},
        files={"file": ("food.jpg", b"fake-image", "image/jpeg")},
    )

    assert response.status_code == 201
    assert response.json()["image_id"]


def test_rate_limit_blocks_repeated_expensive_calls(tmp_path: Path):
    app = create_app(testing=True, storage_root=tmp_path, rate_limit_per_minute=2)
    client = TestClient(app)
    headers = {"X-Client-Key": "dev-client-key"}

    first = client.post("/api/v1/locations/nearby", headers=headers, json={"latitude": 31.23, "longitude": 121.47})
    second = client.post("/api/v1/locations/nearby", headers=headers, json={"latitude": 31.23, "longitude": 121.47})
    third = client.post("/api/v1/locations/nearby", headers=headers, json={"latitude": 31.23, "longitude": 121.47})

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 429
    assert third.json()["detail"] == "rate limit exceeded"


def test_health_does_not_require_api_key(tmp_path: Path):
    app = create_app(testing=True, storage_root=tmp_path)
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
