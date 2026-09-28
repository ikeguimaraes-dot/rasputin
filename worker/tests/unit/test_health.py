from fastapi.testclient import TestClient

from auditoria.main import create_app


def test_health_returns_ok_envelope():
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"success": True, "data": {"status": "ok"}, "error": None}
