from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Faction(Base):
    __tablename__ = "factions"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)
    emblem: Mapped[str] = mapped_column(String(10), default="🦁")
    color: Mapped[str] = mapped_column(String(10), default="#00e5a0")
    points: Mapped[int] = mapped_column(Integer, default=0)

    members: Mapped[list["User"]] = relationship(back_populates="faction")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    faction_id: Mapped[int] = mapped_column(ForeignKey("factions.id"))
    points: Mapped[int] = mapped_column(Integer, default=0)
    streak: Mapped[int] = mapped_column(Integer, default=0)
    last_checkin_day: Mapped[str | None] = mapped_column(String(10), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    faction: Mapped[Faction] = relationship(back_populates="members")
    checkins: Mapped[list["CheckIn"]] = relationship(back_populates="user")


class Quest(Base):
    __tablename__ = "quests"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(String(300), default="")
    icon: Mapped[str] = mapped_column(String(10), default="📍")
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    radius_m: Mapped[int] = mapped_column(Integer, default=75)
    points: Mapped[int] = mapped_column(Integer, default=50)
    active: Mapped[int] = mapped_column(Integer, default=1)

    checkins: Mapped[list["CheckIn"]] = relationship(back_populates="quest")


class DualQuest(Base):
    """Two players, one quest, one time window. Both check in before expiry → allies + bonus.

    New table only (no ALTER on existing tables) so create_all() upgrades prod safely.
    Timestamps are unix epochs to behave identically on SQLite and Postgres.
    pair_key is `min(a,b):max(a,b)` so the partial unique index below prevents duplicate
    open (pending or active) duals between the same two players — same expression works on
    SQLite and Postgres.
    """

    __tablename__ = "dual_quests"

    id: Mapped[int] = mapped_column(primary_key=True)
    quest_id: Mapped[int] = mapped_column(ForeignKey("quests.id"))
    challenger_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    challenged_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    pair_key: Mapped[str] = mapped_column(String(24))
    status: Mapped[str] = mapped_column(String(10), default="pending")  # pending|active|completed|expired|declined
    bonus_points: Mapped[int] = mapped_column(Integer, default=100)
    created_epoch: Mapped[int] = mapped_column(Integer)
    expires_epoch: Mapped[int | None] = mapped_column(Integer, nullable=True)  # set on accept
    challenger_done_epoch: Mapped[int | None] = mapped_column(Integer, nullable=True)
    challenged_done_epoch: Mapped[int | None] = mapped_column(Integer, nullable=True)

    quest: Mapped[Quest] = relationship()
    challenger: Mapped[User] = relationship(foreign_keys=[challenger_id])
    challenged: Mapped[User] = relationship(foreign_keys=[challenged_id])

    __table_args__ = (
        Index(
            "ix_dual_open_pair",
            "pair_key",
            unique=True,
            sqlite_where=text("status IN ('pending','active')"),
            postgresql_where=text("status IN ('pending','active')"),
        ),
    )

    @staticmethod
    def make_pair_key(a: int, b: int) -> str:
        lo, hi = (a, b) if a <= b else (b, a)
        return f"{lo}:{hi}"


class CheckIn(Base):
    __tablename__ = "checkins"
    # A quest is completable once per user per (EAT) day — this drives the daily loop
    __table_args__ = (UniqueConstraint("user_id", "quest_id", "day_key", name="uq_daily_checkin"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    quest_id: Mapped[int] = mapped_column(ForeignKey("quests.id"), index=True)
    day_key: Mapped[str] = mapped_column(String(10))
    points_awarded: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped[User] = relationship(back_populates="checkins")
    quest: Mapped[Quest] = relationship(back_populates="checkins")
