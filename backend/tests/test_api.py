from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app


def test_health_endpoint_reports_dependencies():
    app = create_app(testing=True)
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert "mysql" in response.json()["dependencies"]
    assert "redis" in response.json()["dependencies"]


def test_upload_endpoint_stores_image_and_returns_image_id(tmp_path: Path):
    app = create_app(testing=True, storage_root=tmp_path)
    client = TestClient(app)

    response = client.post(
        "/api/v1/images",
        headers={"X-Client-Key": "dev-client-key"},
        files={"file": ("food.jpg", b"fake-image", "image/jpeg")},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["image_id"]
    assert body["relative_path"].endswith(".jpg")
    assert (tmp_path / body["relative_path"]).exists()


def test_analyze_endpoint_returns_mvp_fields(tmp_path: Path):
    app = create_app(testing=True, storage_root=tmp_path)
    client = TestClient(app)
    upload = client.post(
        "/api/v1/images",
        headers={"X-Client-Key": "dev-client-key"},
        files={"file": ("food.jpg", b"fake-image", "image/jpeg")},
    ).json()

    response = client.post(
        "/api/v1/analyses",
        headers={"X-Client-Key": "dev-client-key"},
        json={
            "image_id": upload["image_id"],
            "image_path": str(tmp_path / upload["relative_path"]),
            "user_profile": {"conditions": ["diabetes"], "goals": ["控糖"]},
            "location_choice": {"kind": "home"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["foods"]
    assert body["cuisine"]["primary_type"]
    assert body["total_calories_range"]
    assert body["total_cost_range"]
    assert body["restaurant_summary"] is None
