from fastapi.testclient import TestClient
from main import app

client = TestClient(app=app)

def test_get_all_employees(): # what if the db is empty but the code works?
    response = client.get("/employee")
    assert response.status_code == 200

