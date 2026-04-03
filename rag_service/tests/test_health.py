from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200

def test_rag_search_endpoint_exists():
    response = client.get("/rag/search")
    assert response.status_code != 404