import os
from fastapi.testclient import TestClient

# Ustawienie tymczasowej bazy SQLite na potrzeby testu CI
os.environ["DATABASE_URL"] = "sqlite:///./test_ci.db"
os.environ["SECRET_KEY"] = "ci-test-secret-key-12345"

from app.main import app

def test_read_main():
    # Użycie bloku 'with' wymusza uruchomienie zdarzeń 'startup' (tworzenie tabel w bazie)
    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 200

def test_swagger_docs():
    with TestClient(app) as client:
        response = client.get("/docs")
        assert response.status_code == 200
