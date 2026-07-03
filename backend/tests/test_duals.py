import os

os.environ["DATABASE_URL"] = "sqlite:///./test_kithfun_duals.db"

import pytest
from fastapi.testclient import TestClient

from app import duals as duals_mod
from app.db import Base, engine
from app.main import app


@pytest.fixture()
def client():
    Base.metadata.drop_all(engine)
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(engine)


def make_user(client, name):
    r = client.post("/api/auth/register", json={"username": name, "password": "secret1"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def challenge(client, headers, target):
    return client.post("/api/duals/challenge", json={"username": target}, headers=headers)


def checkin_at_quest(client, headers, quest):
    return client.post(
        f"/api/quests/{quest['id']}/checkin",
        json={"lat": quest["lat"], "lng": quest["lng"]},
        headers=headers,
    )


def test_full_dual_flow(client):
    alice = make_user(client, "alice")
    bob = make_user(client, "bob")

    r = challenge(client, alice, "bob")
    assert r.status_code == 200, r.text
    dual = r.json()
    assert dual["status"] == "pending"
    assert dual["partner"] == "bob"

    # bob sees it as incoming and accepts
    bob_view = client.get("/api/duals", headers=bob).json()[0]
    assert bob_view["incoming"] is True
    r = client.post(f"/api/duals/{dual['id']}/accept", headers=bob)
    assert r.status_code == 200
    assert r.json()["status"] == "active"

    quest = next(
        q for q in client.get("/api/quests").json() if q["id"] == dual["quest"]["id"]
    )

    # alice checks in — her side done, not completed yet
    r = checkin_at_quest(client, alice, quest)
    assert r.status_code == 200
    state = client.get("/api/duals", headers=alice).json()[0]
    assert state["you_done"] is True and state["partner_done"] is False
    assert state["status"] == "active"

    # bob checks in — dual completes, both earn quest + bonus points
    r = checkin_at_quest(client, bob, quest)
    assert r.status_code == 200
    assert "Dual Quest complete" in r.json()["message"]

    for headers in (alice, bob):
        me = client.get("/api/me", headers=headers).json()
        assert me["points"] == quest["points"] + duals_mod.DUAL_BONUS
    assert client.get("/api/duals", headers=alice).json()[0]["status"] == "completed"


def test_cannot_challenge_self_or_ghost(client):
    alice = make_user(client, "alice")
    assert challenge(client, alice, "alice").status_code == 400
    assert challenge(client, alice, "nobody_here").status_code == 400


def test_no_duplicate_open_dual(client):
    alice = make_user(client, "alice")
    make_user(client, "bob")
    assert challenge(client, alice, "bob").status_code == 200
    r = challenge(client, alice, "bob")
    assert r.status_code == 400
    assert "already have" in r.json()["detail"]


def test_only_challenged_can_accept(client):
    alice = make_user(client, "alice")
    make_user(client, "bob")
    dual = challenge(client, alice, "bob").json()
    r = client.post(f"/api/duals/{dual['id']}/accept", headers=alice)
    assert r.status_code == 400


def test_decline(client):
    alice = make_user(client, "alice")
    bob = make_user(client, "bob")
    dual = challenge(client, alice, "bob").json()
    r = client.post(f"/api/duals/{dual['id']}/decline", headers=bob)
    assert r.status_code == 200
    assert r.json()["status"] == "declined"
    # declined pair can start fresh
    assert challenge(client, bob, "alice").status_code == 200


def test_active_dual_expires(client, monkeypatch):
    alice = make_user(client, "alice")
    bob = make_user(client, "bob")
    dual = challenge(client, alice, "bob").json()
    client.post(f"/api/duals/{dual['id']}/accept", headers=bob)

    real_time = duals_mod._now()
    monkeypatch.setattr(duals_mod, "_now", lambda: real_time + duals_mod.ACTIVE_WINDOW_S + 60)
    state = client.get("/api/duals", headers=alice).json()[0]
    assert state["status"] == "expired"

    # late check-in gives quest points but no dual credit
    quest = next(q for q in client.get("/api/quests").json() if q["id"] == dual["quest"]["id"])
    r = checkin_at_quest(client, alice, quest)
    assert r.status_code == 200
    assert "Dual Quest" not in r.json()["message"]


def test_dual_picks_quest_not_done_today(client):
    alice = make_user(client, "alice")
    make_user(client, "bob")
    quests = client.get("/api/quests").json()
    # alice completes 5 of 6 quests
    for q in quests[:5]:
        assert checkin_at_quest(client, alice, q).status_code == 200
    dual = challenge(client, alice, "bob").json()
    assert dual["quest"]["id"] == quests[5]["id"]


def test_suggestions_exclude_self_and_open_partners(client):
    alice = make_user(client, "alice")
    make_user(client, "bob")
    make_user(client, "carol")
    challenge(client, alice, "bob")
    names = {s["username"] for s in client.get("/api/duals/suggestions", headers=alice).json()}
    assert "alice" not in names
    assert "bob" not in names
    assert "carol" in names


# ---------- regression: five bugs surfaced by adversarial review ----------


def test_checkin_during_pending_still_credits_after_accept(client):
    """Reg #1: alice checks in while dual is still pending; when bob accepts and
    checks in, alice's earlier check-in must credit her side of the dual."""
    alice = make_user(client, "alice")
    bob = make_user(client, "bob")
    dual = challenge(client, alice, "bob").json()
    quest = next(q for q in client.get("/api/quests").json() if q["id"] == dual["quest"]["id"])

    # alice checks in BEFORE bob accepts (dual is still pending)
    assert checkin_at_quest(client, alice, quest).status_code == 200

    # bob accepts, then checks in — dual must complete
    assert client.post(f"/api/duals/{dual['id']}/accept", headers=bob).status_code == 200
    r = checkin_at_quest(client, bob, quest)
    assert r.status_code == 200
    assert "Dual Quest complete" in r.json()["message"]

    for headers in (alice, bob):
        me = client.get("/api/me", headers=headers).json()
        assert me["points"] == quest["points"] + duals_mod.DUAL_BONUS


def test_accept_completes_when_both_already_checked_in(client):
    """Reg #1b: if BOTH players checked in during pending, accepting must
    immediately complete the dual and award the bonus."""
    alice = make_user(client, "alice")
    bob = make_user(client, "bob")
    dual = challenge(client, alice, "bob").json()
    quest = next(q for q in client.get("/api/quests").json() if q["id"] == dual["quest"]["id"])

    checkin_at_quest(client, alice, quest)
    checkin_at_quest(client, bob, quest)
    r = client.post(f"/api/duals/{dual['id']}/accept", headers=bob)
    assert r.status_code == 200
    assert r.json()["status"] == "completed"

    for headers in (alice, bob):
        me = client.get("/api/me", headers=headers).json()
        assert me["points"] == quest["points"] + duals_mod.DUAL_BONUS


def test_no_duplicate_open_duals_at_db_level(client):
    """Reg #4: even if the app-layer existence check is bypassed (e.g. concurrent
    inserts), the DB partial unique index must prevent two open duals for the pair."""
    from sqlalchemy.exc import IntegrityError

    from app.db import SessionLocal
    from app.models import DualQuest, User

    make_user(client, "alice")
    make_user(client, "bob")
    with SessionLocal() as db:
        a = db.query(User).filter_by(username="alice").one()
        b = db.query(User).filter_by(username="bob").one()
        quest_id = client.get("/api/quests").json()[0]["id"]
        now = int(time.time())
        db.add(DualQuest(
            quest_id=quest_id, challenger_id=a.id, challenged_id=b.id,
            pair_key=DualQuest.make_pair_key(a.id, b.id),
            created_epoch=now, bonus_points=100,
        ))
        db.commit()
        # Reverse direction should also be blocked — pair_key normalizes order
        db.add(DualQuest(
            quest_id=quest_id, challenger_id=b.id, challenged_id=a.id,
            pair_key=DualQuest.make_pair_key(b.id, a.id),
            created_epoch=now, bonus_points=100,
        ))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


def test_new_challenge_ok_after_previous_dual_ends(client):
    """Reg #4b: partial index must NOT block a new challenge once the previous
    one has completed/declined/expired — the pair_key row leaves the index."""
    alice = make_user(client, "alice")
    bob = make_user(client, "bob")
    dual = challenge(client, alice, "bob").json()
    assert client.post(f"/api/duals/{dual['id']}/decline", headers=bob).status_code == 200
    # A fresh challenge in the reverse direction must succeed.
    assert challenge(client, bob, "alice").status_code == 200


def test_suggestions_respect_old_open_partners_beyond_recent_cap(client):
    """Reg #5: suggestions must exclude anyone with an open dual, even if that
    dual is older than the 20 most recent records (my_duals is capped at 20)."""
    alice = make_user(client, "alice")
    make_user(client, "bob")
    make_user(client, "carol")

    # Alice's oldest open record: pending challenge to bob (dual #1)
    assert challenge(client, alice, "bob").status_code == 200

    # Now stuff Alice's history with 25 finished (declined) challenges so #1 is
    # pushed off my_duals's 20-item window.
    for i in range(25):
        u = f"filler{i}"
        u_headers = make_user(client, u)
        r = challenge(client, alice, u).json()
        client.post(f"/api/duals/{r['id']}/decline", headers=u_headers)

    names = {s["username"] for s in client.get("/api/duals/suggestions", headers=alice).json()}
    assert "bob" not in names, "old pending dual with bob should still exclude him"


def test_dual_credit_failure_never_swallows_checkin_points(client, monkeypatch):
    """Reg #3: if duals.on_checkin blows up, the check-in points must still be saved."""
    alice = make_user(client, "alice")
    make_user(client, "bob")
    challenge(client, alice, "bob")  # creates open dual — on_checkin will look for it

    quest = client.get("/api/quests").json()[0]

    def boom(*_a, **_kw):
        raise RuntimeError("simulated dual credit failure")

    monkeypatch.setattr("app.duals.on_checkin", boom)
    r = checkin_at_quest(client, alice, quest)
    assert r.status_code == 200, r.text
    assert r.json()["points_awarded"] == quest["points"]
    me = client.get("/api/me", headers=alice).json()
    assert me["points"] == quest["points"]


import time  # keep at bottom — only used by the DB-level regression test
