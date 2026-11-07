import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(graph):
    from app.main import app

    return TestClient(app)


def test_health_and_registry(client):
    assert client.get("/health").json()["ok"]
    r = client.get("/api/registry/gstin/37IHKXV5167L1ZS").json()
    assert r["found"] and r["status"] == "Cancelled"
    assert client.get("/api/registry/gstin/37IHKXV5167L1ZX").json()["valid_format"] is False
    assert client.get("/api/registry/udyam/UDYAM-WB-00-5053330").json()["found"]
    assert client.get("/api/registry/udyam/UDYAM-WB-00-5053330?gstin=19EOGXH4115Y1ZL").json()["gst_match"] is True
    other = client.get("/api/registry/udyam/UDYAM-WB-00-5053330?gstin=27XUIXG0767D1ZP").json()
    assert other["gst_match"] is False and other["gst_trade_name"] == "Ganesh Woodcraft"


def test_journey_flow_and_wrong_kind(client):
    j = client.post("/api/journeys", json={"lang": "en"}).json()
    jid = j["journey_id"]
    assert j["pending"]["kind"] == "chat" and j["messages"]
    r = client.post(f"/api/journeys/{jid}/resume", json={"value": {"kind": "quote", "action": "accept"}})
    assert r.status_code == 409
    j = client.post(f"/api/journeys/{jid}/resume", json={"value": {
        "kind": "chat", "text": "Kirana store in Lucknow, 2 people, one shop, no GST, using mobile hotspot, need UPI billing"}}).json()
    assert j["pending"]["kind"] == "quote" and j["quote"]["monthly_total"] > 0


def test_digilocker_masks_identifiers(client):
    jid = client.post("/api/journeys", json={}).json()["journey_id"]
    r = client.post(f"/api/journeys/{jid}/digilocker", json={"gstin": "19EOGXH4115Y1ZL"}).json()
    g = r["documents"][0]["fields"]["gstin"]
    assert g.startswith("19") and "•" in g


def test_backoffice_requires_key(client):
    assert client.get("/api/backoffice/summary").status_code == 401
    r = client.get("/api/backoffice/leads?limit=5", headers={"X-Backoffice-Key": "demo"}).json()
    assert len(r["leads"]) == 5 and all(0 <= l["score"] <= 1 for l in r["leads"])


def test_crash_is_json_500_with_cors_header(client, monkeypatch):
    from app.routers import journey as journey_router

    def boom(*a, **k):
        raise RuntimeError("db connection closed")

    monkeypatch.setattr(journey_router, "get_graph", boom)
    origin = "https://airtel-sync-26-abc123-team.vercel.app"
    r = client.post("/api/journeys", json={"lang": "en"}, headers={"Origin": origin})
    assert r.status_code == 500 and "try again" in r.json()["detail"]
    assert r.headers.get("access-control-allow-origin") == origin
