from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200

def test_docs_available():
    response = client.get("/docs")
    assert response.status_code == 200