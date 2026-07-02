"""Idempotent seed: four houses + demo campus quests around CAMPUS_LAT/LNG."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import CAMPUS_LAT, CAMPUS_LNG
from .models import Faction, Quest

FACTIONS = [
    ("House Simba", "🦁", "#f5a623"),
    ("House Chui", "🐆", "#00e5a0"),
    ("House Ndovu", "🐘", "#4a9eff"),
    ("House Kifaru", "🦏", "#e0508c"),
]

# Offsets in degrees (~111km per degree lat); quests ring the campus center
QUESTS = [
    ("Library Grind", "Hit the books where the silence lives.", "📚", 0.0012, 0.0008, 75, 50),
    ("Lecture Legend", "Show up. Half of success is attendance.", "🎓", -0.0010, 0.0014, 75, 40),
    ("Cafeteria Social", "Break bread, make allies.", "🍛", 0.0006, -0.0013, 60, 30),
    ("Lab Rat", "Where the real experiments happen.", "🧪", -0.0015, -0.0006, 75, 60),
    ("Field Day", "Touch grass. Literally.", "⚽", 0.0020, -0.0002, 100, 40),
    ("Innovation Hub", "Ship something. Anything.", "💡", -0.0004, 0.0021, 60, 70),
]


def seed(db: Session) -> None:
    if db.execute(select(Faction).limit(1)).scalar_one_or_none() is None:
        for name, emblem, color in FACTIONS:
            db.add(Faction(name=name, emblem=emblem, color=color))
    if db.execute(select(Quest).limit(1)).scalar_one_or_none() is None:
        for title, desc, icon, dlat, dlng, radius, points in QUESTS:
            db.add(
                Quest(
                    title=title,
                    description=desc,
                    icon=icon,
                    lat=CAMPUS_LAT + dlat,
                    lng=CAMPUS_LNG + dlng,
                    radius_m=radius,
                    points=points,
                )
            )
    db.commit()
