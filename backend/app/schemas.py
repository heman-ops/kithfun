from pydantic import BaseModel, Field


class RegisterIn(BaseModel):
    username: str = Field(min_length=3, max_length=30, pattern=r"^[a-zA-Z0-9_]+$")
    password: str = Field(min_length=6, max_length=100)


class LoginIn(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    token: str


class FactionOut(BaseModel):
    id: int
    name: str
    emblem: str
    color: str
    points: int

    model_config = {"from_attributes": True}


class MeOut(BaseModel):
    id: int
    username: str
    points: int
    streak: int
    faction: FactionOut
    completed_today: list[int]


class QuestOut(BaseModel):
    id: int
    title: str
    description: str
    icon: str
    lat: float
    lng: float
    radius_m: int
    points: int

    model_config = {"from_attributes": True}


class CheckInIn(BaseModel):
    lat: float
    lng: float


class CheckInOut(BaseModel):
    ok: bool
    points_awarded: int
    total_points: int
    streak: int
    faction_points: int
    message: str


class PlayerRank(BaseModel):
    username: str
    points: int
    streak: int
    faction_name: str
    faction_emblem: str


class LeaderboardOut(BaseModel):
    factions: list[FactionOut]
    players: list[PlayerRank]


class MapConfigOut(BaseModel):
    campus_name: str
    lat: float
    lng: float
    zoom: int = 16
