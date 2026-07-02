"""Quest engine: check-in validation, scoring, streaks, leaderboards."""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .geo import haversine_m, local_day_key, previous_day_key
from .models import CheckIn, Faction, Quest, User


class CheckInError(Exception):
    def __init__(self, message: str):
        self.message = message


def assign_faction(db: Session) -> Faction:
    """Keep houses balanced: new players join the smallest one."""
    counts = dict(
        db.execute(
            select(User.faction_id, func.count(User.id)).group_by(User.faction_id)
        ).all()
    )
    factions = db.execute(select(Faction)).scalars().all()
    return min(factions, key=lambda f: counts.get(f.id, 0))


def perform_checkin(db: Session, user: User, quest: Quest, lat: float, lng: float) -> CheckIn:
    if not quest.active:
        raise CheckInError("This quest is not active.")

    distance = haversine_m(lat, lng, quest.lat, quest.lng)
    if distance > quest.radius_m:
        raise CheckInError(f"Too far away — you are ~{int(distance)}m out, get within {quest.radius_m}m.")

    day = local_day_key()
    already = db.execute(
        select(CheckIn).where(
            CheckIn.user_id == user.id, CheckIn.quest_id == quest.id, CheckIn.day_key == day
        )
    ).scalar_one_or_none()
    if already:
        raise CheckInError("Already completed today — come back tomorrow.")

    if user.last_checkin_day == day:
        pass  # streak already counted today
    elif user.last_checkin_day == previous_day_key(day):
        user.streak += 1
    else:
        user.streak = 1
    user.last_checkin_day = day

    checkin = CheckIn(user_id=user.id, quest_id=quest.id, day_key=day, points_awarded=quest.points)
    user.points += quest.points
    user.faction.points += quest.points
    db.add(checkin)
    db.commit()
    return checkin


def leaderboard(db: Session, top_n: int = 10) -> dict:
    factions = db.execute(select(Faction).order_by(Faction.points.desc())).scalars().all()
    players = db.execute(select(User).order_by(User.points.desc()).limit(top_n)).scalars().all()
    return {
        "factions": [
            {"id": f.id, "name": f.name, "emblem": f.emblem, "color": f.color, "points": f.points}
            for f in factions
        ],
        "players": [
            {
                "username": u.username,
                "points": u.points,
                "streak": u.streak,
                "faction_name": u.faction.name,
                "faction_emblem": u.faction.emblem,
            }
            for u in players
        ],
    }


def completed_today(db: Session, user: User) -> list[int]:
    day = local_day_key()
    rows = db.execute(
        select(CheckIn.quest_id).where(CheckIn.user_id == user.id, CheckIn.day_key == day)
    ).all()
    return [r[0] for r in rows]
