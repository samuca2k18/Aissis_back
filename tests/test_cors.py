from fastapi.testclient import TestClient

from app.main import create_app
from app.settings import settings


def test_cors_allows_patch_preflight(monkeypatch):
    monkeypatch.setattr(settings, "SCHEDULER_ENABLED", False)
    app = create_app()

    with TestClient(app) as client:
        response = client.options(
            "/auth/users/1/status",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "PATCH",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )

    assert response.status_code == 200


def test_bootstrap_admin_requires_bootstrap_header(monkeypatch):
    monkeypatch.setattr(settings, "SCHEDULER_ENABLED", False)
    monkeypatch.setattr(settings, "AUTH_BOOTSTRAP_TOKEN", "token-seguro")
    app = create_app()

    with TestClient(app) as client:
        response = client.post(
            "/auth/bootstrap-admin",
            json={
                "nome": "Admin Temp",
                "email": "admin-temp@example.com",
                "password": "SenhaSegura123",
            },
        )

    assert response.status_code == 401
