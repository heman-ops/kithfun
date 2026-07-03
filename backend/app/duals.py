"""Dual Quest engine: quest-based social matching.

A challenge picks a quest neither player has completed today. On accept, a
2-hour window opens; each player's normal geofenced check-in at that quest
counts as their side. Both sides done before expiry → completed: both players
(and their factions) earn the bonus. Expiry is lazy — evaluated on read.
"""
import random
import time

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .geo import local_day_key
from .models import CheckIn, DualQuest, Quest, User

ACCEPT_WINDOW_S = 24 * 3600   # pending challenges live 24h
ACTIVE_WINDOW_S = 2 * 3600    # both must check in within 2h of accepting
DUAL_BONUS = 100


class DualError(Exception):
    def __init__(self, message: str):
        self.message = message


def _now() -> int:
    return int(time.time())


def _expire_if_due(dual: DualQuest, now: int) -> None:
    if dual.status == "pending" and now > dual.created_epoch + ACCEPT_WINDOW_S:
        dual.status = "expired"
    elif dual.status == "active" and dual.expires_epoch and now > dual.expires_epoch:
        dual.status = "expired"


def _complete_and_award(dual: DualQuest) -> None:
    dual.status = "completed"
    for player in (dual.challenger, dual.challenged):
        player.points += dual.bonus_points
        player.faction.points += dual.bonus_points


def _quests_done_today(db: Session, user_id: int) -> set[int]:
    day = local_day_key()
    rows = db.execute(
        select(CheckIn.quest_id).where(CheckIn.user_id == user_id, CheckIn.day_key == day)
    ).all()
    return {r[0] for r in rows}


def create_challenge(db: Session, challenger: User, challenged_username: str) -> DualQuest:
    challenged = db.execute(
        select(User).where(User.username == challenged_username)
    ).scalar_one_or_none()
    if challenged is None:
        raise DualError("No player with that username.")
    if challenged.id == challenger.id:
        raise DualError("You can't challenge yourself — that's just a quest.")

    existing = db.execute(
        select(DualQuest).where(
            DualQuest.status.in_(["pending", "active"]),
            or_(
                (DualQuest.challenger_id == challenger.id) & (DualQuest.challenged_id == challenged.id),
                (DualQuest.challenger_id == challenged.id) & (DualQuest.challenged_id == challenger.id),
            ),
        )
    ).scalars().all()
    now = _now()
    for d in existing:
        _expire_if_due(d, now)
    if any(d.status in ("pending", "active") for d in existing):
        db.commit()
        raise DualError("You already have an open Dual Quest with this player.")

    done = _quests_done_today(db, challenger.id) | _quests_done_today(db, challenged.id)
    quest_query = select(Quest).where(Quest.active == 1)
    if done:
        quest_query = quest_query.where(Quest.id.not_in(done))
    candidates = db.execute(quest_query).scalars().all()
    if not candidates:
        raise DualError("You two have completed every quest today — challenge again tomorrow.")

    dual = DualQuest(
        quest_id=random.choice(candidates).id,
        challenger_id=challenger.id,
        challenged_id=challenged.id,
        pair_key=DualQuest.make_pair_key(challenger.id, challenged.id),
        bonus_points=DUAL_BONUS,
        created_epoch=now,
    )
    db.add(dual)
    try:
        db.commit()
    except IntegrityError:
        # Lost the race with a concurrent challenge between the same pair — the partial
        # unique index on pair_key (WHERE status IN pending|active) blocked us.
        db.rollback()
        raise DualError("You already have an open Dual Quest with this player.")
    return dual


def _get_for_user(db: Session, user: User, dual_id: int) -> DualQuest:
    dual = db.get(DualQuest, dual_id)
    if dual is None or user.id not in (dual.challenger_id, dual.challenged_id):
        raise DualError("Dual Quest not found.")
    _expire_if_due(dual, _now())
    return dual


def accept(db: Session, user: User, dual_id: int) -> DualQuest:
    dual = _get_for_user(db, user, dual_id)
    if dual.status != "pending":
        db.commit()
        raise DualError(f"This challenge is {dual.status}.")
    if user.id != dual.challenged_id:
        raise DualError("Only the challenged player can accept.")
    dual.status = "active"
    dual.expires_epoch = _now() + ACTIVE_WINDOW_S
    # Both players may have already checked in during the pending window — complete now.
    if dual.challenger_done_epoch and dual.challenged_done_epoch:
        _complete_and_award(dual)
    db.commit()
    return dual


def decline(db: Session, user: User, dual_id: int) -> DualQuest:
    dual = _get_for_user(db, user, dual_id)
    if dual.status != "pending":
        db.commit()
        raise DualError(f"This challenge is {dual.status}.")
    if user.id != dual.challenged_id:
        raise DualError("Only the challenged player can decline.")
    dual.status = "declined"
    db.commit()
    return dual


def on_checkin(db: Session, user: User, quest_id: int) -> list[DualQuest]:
    """Credit any open duals for this user+quest; complete when both sides are in.

    Called after a successful geofenced check-in. We credit BOTH pending and active duals —
    if a challenger check-ins in during the pending window (before accept), her side of the
    daily quest is consumed by the normal check-in path, and without crediting the pending
    dual too she'd never be able to earn dual credit for that quest. Completion still
    requires status='active' + both sides done. `SELECT ... FOR UPDATE` serializes the
    race where both partners check in concurrently on Postgres; SQLite serializes writes
    naturally so the same code is safe there.
    """
    now = _now()
    open_duals = db.execute(
        select(DualQuest)
        .where(
            DualQuest.status.in_(["pending", "active"]),
            DualQuest.quest_id == quest_id,
            or_(DualQuest.challenger_id == user.id, DualQuest.challenged_id == user.id),
        )
        .with_for_update()
    ).scalars().all()

    completed = []
    for dual in open_duals:
        _expire_if_due(dual, now)
        if dual.status not in ("pending", "active"):
            continue
        if user.id == dual.challenger_id and dual.challenger_done_epoch is None:
            dual.challenger_done_epoch = now
        elif user.id == dual.challenged_id and dual.challenged_done_epoch is None:
            dual.challenged_done_epoch = now
        if (
            dual.status == "active"
            and dual.challenger_done_epoch
            and dual.challenged_done_epoch
        ):
            _complete_and_award(dual)
            completed.append(dual)
    db.commit()
    return completed


def my_duals(db: Session, user: User, limit: int = 20) -> list[DualQuest]:
    duals = db.execute(
        select(DualQuest)
        .where(or_(DualQuest.challenger_id == user.id, DualQuest.challenged_id == user.id))
        .order_by(DualQuest.id.desc())
        .limit(limit)
    ).scalars().all()
    now = _now()
    for d in duals:
        _expire_if_due(d, now)
    db.commit()
    return duals


def suggestions(db: Session, user: User, limit: int = 5) -> list[User]:
    """A few other players to challenge — excludes yourself and open-dual partners.

    Queries open duals directly (not through my_duals, which caps at the 20 most recent)
    so an older-than-20 open dual is still respected.
    """
    now = _now()
    open_duals = db.execute(
        select(DualQuest).where(
            DualQuest.status.in_(["pending", "active"]),
            or_(DualQuest.challenger_id == user.id, DualQuest.challenged_id == user.id),
        )
    ).scalars().all()
    open_partner_ids: set[int] = set()
    for d in open_duals:
        _expire_if_due(d, now)
        if d.status in ("pending", "active"):
            open_partner_ids.update({d.challenger_id, d.challenged_id})
    open_partner_ids.discard(user.id)
    db.commit()

    query = select(User).where(User.id != user.id)
    if open_partner_ids:
        query = query.where(User.id.not_in(open_partner_ids))
    return db.execute(query.order_by(func.random()).limit(limit)).scalars().all()


def serialize(dual: DualQuest, viewer: User) -> dict:
    partner = dual.challenged if viewer.id == dual.challenger_id else dual.challenger
    return {
        "id": dual.id,
        "status": dual.status,
        "quest": {
            "id": dual.quest.id,
            "title": dual.quest.title,
            "icon": dual.quest.icon,
            "lat": dual.quest.lat,
            "lng": dual.quest.lng,
        },
        "partner": partner.username,
        "incoming": viewer.id == dual.challenged_id,
        "bonus_points": dual.bonus_points,
        "expires_epoch": dual.expires_epoch,
        "you_done": (
            dual.challenger_done_epoch if viewer.id == dual.challenger_id else dual.challenged_done_epoch
        ) is not None,
        "partner_done": (
            dual.challenged_done_epoch if viewer.id == dual.challenger_id else dual.challenger_done_epoch
        ) is not None,
    }
