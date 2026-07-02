from contextlib import asynccontextmanager
from pathlib import Path

import anyio
from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import game, schemas
from .auth import create_token, current_user, hash_password, verify_password
from .config import CAMPUS_LAT, CAMPUS_LNG, CAMPUS_NAME
from .db import Base, SessionLocal, engine, get_db
from .models import Quest, User
from .seed import seed
from .ws import hub

@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed(db)
    yield


app = FastAPI(title="KithFun API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- auth ----------

@app.post("/api/auth/register", response_model=schemas.TokenOut)
def register(body: schemas.RegisterIn, db: Session = Depends(get_db)):
    exists = db.execute(select(User).where(User.username == body.username)).scalar_one_or_none()
    if exists:
        raise HTTPException(409, "Username already taken")
    faction = game.assign_faction(db)
    user = User(
        username=body.username,
        password_hash=hash_password(body.password),
        faction_id=faction.id,
    )
    db.add(user)
    db.commit()
    return {"token": create_token(user.id)}


@app.post("/api/auth/login", response_model=schemas.TokenOut)
def login(body: schemas.LoginIn, db: Session = Depends(get_db)):
    user = db.execute(select(User).where(User.username == body.username)).scalar_one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Invalid username or password")
    return {"token": create_token(user.id)}


# ---------- game ----------

@app.get("/api/me", response_model=schemas.MeOut)
def me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return {
        "id": user.id,
        "username": user.username,
        "points": user.points,
        "streak": user.streak,
        "faction": user.faction,
        "completed_today": game.completed_today(db, user),
    }


@app.get("/api/quests", response_model=list[schemas.QuestOut])
def quests(db: Session = Depends(get_db)):
    return db.execute(select(Quest).where(Quest.active == 1)).scalars().all()


@app.post("/api/quests/{quest_id}/checkin", response_model=schemas.CheckInOut)
async def checkin(
    quest_id: int,
    body: schemas.CheckInIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    quest = db.get(Quest, quest_id)
    if quest is None:
        raise HTTPException(404, "Quest not found")
    try:
        result = await anyio.to_thread.run_sync(
            game.perform_checkin, db, user, quest, body.lat, body.lng
        )
    except game.CheckInError as e:
        raise HTTPException(400, e.message)

    await hub.broadcast({"type": "leaderboard", **game.leaderboard(db)})
    return {
        "ok": True,
        "points_awarded": result.points_awarded,
        "total_points": user.points,
        "streak": user.streak,
        "faction_points": user.faction.points,
        "message": f"+{result.points_awarded} pts for {user.faction.name}!",
    }


@app.get("/api/leaderboard", response_model=schemas.LeaderboardOut)
def get_leaderboard(db: Session = Depends(get_db)):
    return game.leaderboard(db)


@app.get("/api/map/config", response_model=schemas.MapConfigOut)
def map_config():
    return {"campus_name": CAMPUS_NAME, "lat": CAMPUS_LAT, "lng": CAMPUS_LNG, "zoom": 16}


@app.websocket("/ws/leaderboard")
async def ws_leaderboard(ws: WebSocket):
    await hub.connect(ws)
    try:
        while True:
            await ws.receive_text()  # keepalive pings from client
    except WebSocketDisconnect:
        await hub.disconnect(ws)


# ---------- frontend (single-deploy: API + PWA from one service) ----------

_frontend = Path(__file__).resolve().parents[2] / "frontend"
if _frontend.is_dir():
    app.mount("/", StaticFiles(directory=_frontend, html=True), name="frontend")
