import os
import tempfile

os.environ["DATA_DIR"] = tempfile.mkdtemp()
os.environ["LLM_PROVIDER"] = "offline"
os.environ["RATE_LIMIT_PER_MIN"] = "1000"

from fastapi.testclient import TestClient  # noqa: E402

from app.server import app  # noqa: E402

client = TestClient(app)
SID = "test-session-123"


def test_health():
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["ok"] and r.json()["passages"] > 0


def test_demo_page_and_widget_are_served():
    assert "widget.js" in client.get("/").text
    assert "SupportBot" in client.get("/static/widget.js").text


def test_chat():
    r = client.post("/api/chat", json={"message": "Do you sell scooters?", "session_id": SID})
    body = r.json()
    assert r.status_code == 200 and "scooters" in body["answer"] and body["handoff"] is False


def test_rejects_bad_session_id():
    r = client.post("/api/chat", json={"message": "hi", "session_id": "../../etc"})
    assert r.status_code == 400


def test_rejects_overlong_message():
    r = client.post("/api/chat", json={"message": "x" * 1001, "session_id": SID})
    assert r.status_code == 422


def test_lead_validation():
    bad = client.post("/api/lead", json={"session_id": SID, "name": "Sam", "email": "not-an-email"})
    good = client.post("/api/lead", json={"session_id": SID, "name": "Sam", "email": "sam@example.com"})
    assert bad.status_code == 422 and good.status_code == 200
