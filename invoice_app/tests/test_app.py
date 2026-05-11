from app import create_app
from config import AppConfig


def make_app(tmp_path):
    app = create_app(AppConfig(database_path=tmp_path / "test.sqlite3"))
    app.config.update(TESTING=True)
    return app


def test_health_endpoint_exposes_fields(tmp_path):
    client = make_app(tmp_path).test_client()

    response = client.get("/api/health")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert "发票号码" in payload["fields"]


def test_records_status_requires_existing_record(tmp_path):
    client = make_app(tmp_path).test_client()

    response = client.patch("/api/records/status", json={"key": "missing", "status": "已报销"})

    assert response.status_code == 404
    assert response.get_json()["code"] == "not_found"
