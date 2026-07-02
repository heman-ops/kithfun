# Deploying KithFun

Total hosting cost: **$0/month**.

## 1. Live demo — GitHub Pages (already set up)

Every push to `main` that touches `frontend/**` auto-deploys the PWA in **demo mode** to:

> **https://heman-ops.github.io/kithfun/**

Demo mode is fully client-side (localStorage): no accounts, quests spawn around the campus center, and you can tap the map to teleport. Perfect for showing people the concept from a WhatsApp link.

## 2. Full app — Render + Neon (two free accounts, ~10 minutes)

The real game (shared leaderboards, real accounts, live WebSocket updates) needs the FastAPI backend and a persistent Postgres database.

### Step A — Neon (free Postgres, never expires)

1. Go to https://neon.tech → **Sign up with GitHub**.
2. Create a project (pick the **Frankfurt** region — closest to Nairobi).
3. Copy the **connection string** (starts with `postgresql://...`).

Free plan: 0.5 GB storage, scale-to-zero with auto-resume, no credit card.

### Step B — Render (free web service)

1. Go to https://render.com → **Sign up with GitHub**.
2. **New → Blueprint** → select the `heman-ops/kithfun` repo. Render reads [render.yaml](../render.yaml) and configures everything.
3. When prompted for `DATABASE_URL`, paste the Neon connection string.
4. Deploy. Your app goes live at `https://kithfun.onrender.com` (or similar).

Free plan notes:
- Spins down after 15 min without traffic; next visit takes ~1 min to wake. Fine for an MVP.
- 750 instance-hours/month — a single always-on-when-used service fits comfortably.
- Do **not** use Render's own free Postgres — it expires after 30 days. Neon doesn't.

### Step C — point the map at your campus

Set these environment variables in the Render dashboard (defaults are University of Nairobi):

| Variable | Example (Kenyatta University) |
|---|---|
| `CAMPUS_NAME` | `Kenyatta University` |
| `CAMPUS_LAT` | `-1.1801` |
| `CAMPUS_LNG` | `36.9352` |

Then edit quest positions in [backend/app/seed.py](../backend/app/seed.py) (offsets from the campus center) — or ask Claude to add an admin API for quest management.

## 3. Local development

```powershell
pip install -r requirements-dev.txt
uvicorn app.main:app --app-dir backend --reload --port 8000
# open http://localhost:8000  (API docs at /docs)
pytest backend/tests -q
```

SQLite (`kithfun.db`) is used automatically when `DATABASE_URL` is not set.

## 4. Map tiles

The map uses free CARTO dark basemaps (with attribution) over OpenStreetMap data. That's fine for a small non-commercial MVP; if the app grows or monetizes, switch the tile URL in `frontend/app.js` to [OpenFreeMap](https://openfreemap.org) (free, unlimited) or a paid MapTiler plan.
