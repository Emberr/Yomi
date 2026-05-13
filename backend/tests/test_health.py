from fastapi.testclient import TestClient

from yomi.config import Settings
from yomi.main import create_app


def test_health_reports_missing_content_db_as_degraded_not_failure(tmp_path):
    content_db = tmp_path / "content.db"
    user_db = tmp_path / "user.db"
    app = create_app(
        Settings(
            content_db_path=content_db,
            user_db_path=user_db,
            behind_https=False,
            base_url="http://testserver",
            log_level="INFO",
        )
    )

    with TestClient(app) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["databases"]["content"]["status"] == "missing"
    assert body["databases"]["content"]["schema_version"] is None
    assert not content_db.exists()
    assert body["databases"]["user"]["status"] == "ok"
    assert body["databases"]["user"]["schema_version"] == "1"

