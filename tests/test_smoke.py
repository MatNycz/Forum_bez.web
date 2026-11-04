import os
from fastapi.testclient import TestClient

# Ustawienie tymczasowej bazy SQLite na potrzeby testu CI
os.environ["DATABASE_URL"] = "sqlite:///./test_ci.db"
os.environ["SECRET_KEY"] = "ci-test-secret-key-12345"

from app.main import app

client = TestClient(app)

def test_read_main():
    response = client.get("/")
    assert response.status_code == 200

def test_swagger_docs():
    response = client.get("/docs")
    assert response.status_code == 200
