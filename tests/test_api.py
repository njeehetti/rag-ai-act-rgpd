from fastapi.testclient import TestClient

from rag_ai_act_rgpd import __version__
from rag_ai_act_rgpd.api import app


def test_health() -> None:
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": __version__}
