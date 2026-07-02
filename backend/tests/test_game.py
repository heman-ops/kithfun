import os

os.environ["DATABASE_URL"] = "sqlite:///./test_kithfun.db"

import pytest
from fastapi.testclient import TestClient

from app.db import Base, engine
from app.main import app


@pytest.fixture()
def client():
    Base.metadata.drop_all(engine)
    with TestClient(app) as c:  # context manager triggers startup (create_all + seed)
        yield c
    Base.metadata.drop_all(engine)


def register(client, name="tester"):
    r = client.post("/api/auth/register", json={"username": name, "password": "secret1"})
    assert r.status_code == 200, r.text
    return r.json()["token"]


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_register_login_me(client):
    token = register(client)
    r = client.post("/api/auth/login", json={"username": "tester", "password": "secret1"})
    assert r.status_code == 200
    me = client.get("/api/me", headers=auth(token)).json()
    assert me["username"] == "tester"
    assert me["points"] == 0
    assert me["faction"]["name"].startswith("House")


def test_duplicate_username_rejected(client):
    register(client)
    r = client.post("/api/auth/register", json={"username": "tester", "password": "secret1"})
    assert r.status_code == 409


def test_checkin_flow(client):
    token = register(client)
    quests = client.get("/api/quests").json()
    assert len(quests) == 6
    q = quests[0]

    # At the quest location → success
    r = client.post(
        f"/api/quests/{q['id']}/checkin",
        json={"lat": q["lat"], "lng": q["lng"]},
        headers=auth(token),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["points_awarded"] == q["points"]
    assert body["streak"] == 1

    # Same quest same day → rejected
    r = client.post(
        f"/api/quests/{q['id']}/checkin",
        json={"lat": q["lat"], "lng": q["lng"]},
        headers=auth(token),
    )
    assert r.status_code == 400
    assert "Already completed" in r.json()["detail"]


def test_checkin_too_far(client):
    token = register(client)
    q = client.get("/api/quests").json()[0]
    r = client.post(
        f"/api/quests/{q['id']}/checkin",
        json={"lat": q["lat"] + 0.01, "lng": q["lng"]},  # ~1.1km away
        headers=auth(token),
    )
    assert r.status_code == 400
    assert "Too far" in r.json()["detail"]


def test_leaderboard_updates(client):
    token = register(client)
    q = client.get("/api/quests").json()[0]
    client.post(
        f"/api/quests/{q['id']}/checkin",
        json={"lat": q["lat"], "lng": q["lng"]},
        headers=auth(token),
    )
    lb = client.get("/api/leaderboard").json()
    assert lb["factions"][0]["points"] == q["points"]
    assert lb["players"][0]["username"] == "tester"


def test_factions_balanced(client):
    seen = set()
    for i in range(4):
        token = register(client, f"user{i}")
        me = client.get("/api/me", headers=auth(token)).json()
        seen.add(me["faction"]["name"])
    assert len(seen) == 4  # four players spread across all four houses
