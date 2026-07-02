# KithFun

**A gamified social metaverse for university campuses in Kenya.**

🎮 **[Play the live demo](https://heman-ops.github.io/kithfun/)** — no install, works on any phone. Tap the map to move around.

KithFun turns the campus into a living game board. Students explore a real map of their university, complete location-based quests, compete in factions — and connect with each other through collaborative "Dual Quests" instead of cold swipes.

## The Concept in One Line

> Campus Quest is the backbone. Social connection is the hook.

## Core Pillars

1. **Campus Quest Engine** — a location-based quest system layered over an interactive campus map, with fog-of-war exploration and daily quests.
2. **Faction System** — every student belongs to a House (dorm, faculty, or year). Quests earn faction points; weekly leaderboards drive competition.
3. **Dual Quest Matching** — the social/dating layer. Matches don't open a chat; they open a shared quest ("both of you reach the library courtyard in the next 2 hours") that turns the awkward first message into a collaborative game.
4. **Social Capital Economy** — a campus currency earned through high-value interactions (design collabs, academic help, community projects), spent on profile customization and access to exclusive zones.
5. **Sub-Arenas** — pluggable competitive hubs inside the map: a Trading Battleground (fantasy finance leagues), a Design Arena (swipe-to-vote design competitions), and a Predict & Prove league (social prop-bets for glory, not money).

See [docs/PRODUCT_BRIEF.md](docs/PRODUCT_BRIEF.md) for the full product vision and [docs/MASTER_PROMPT.md](docs/MASTER_PROMPT.md) for the AI planning prompt that seeds architecture work.

## Stack

| Layer | Choice | Why |
|---|---|---|
| Client | Installable **PWA** (vanilla JS + [Leaflet](https://leafletjs.com)) | No Play Store fee/review, ~100KB payload for data-sensitive users, geolocation works great on Android Chrome |
| Map | CARTO dark basemap tiles (OSM data) | Free with attribution, matches the dark terminal aesthetic |
| Backend | **FastAPI** + SQLAlchemy | Python-first, async WebSockets for live leaderboards |
| Database | SQLite (dev) / **Neon Postgres** (prod) | Neon free tier is permanent and scales to zero |
| Hosting | **GitHub Pages** (demo) + **Render** free tier (full app) | $0/month |

## Quickstart

```powershell
pip install -r requirements-dev.txt
uvicorn app.main:app --app-dir backend --reload --port 8000
# open http://localhost:8000 — API docs at /docs
pytest backend/tests -q
```

Deployment guide: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)

## MVP features (v0.1)

- 🗺️ Dark campus map with geofenced quest zones
- 📍 GPS check-ins (haversine-validated, once per quest per day)
- 🦁 Four houses with balanced auto-assignment and a live faction leaderboard (WebSocket)
- 🔥 Daily streaks (East Africa Time day boundaries)
- 📲 Installable PWA with offline shell
- 🕹️ Zero-backend **demo mode** (GitHub Pages) — tap-to-teleport, localStorage state

## Status

🚀 **MVP scaffold shipped** — playable demo live; Dual Quest matching, sub-arenas, and campus currency are next (see the product brief).

## Target Market

University students in Kenya. Mobile-first, low-latency, M-Pesa-aware.

## License

Not yet chosen — all rights reserved for now.
