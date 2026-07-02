import os
import secrets

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./kithfun.db")
# Render/Heroku-style URLs use postgres://; SQLAlchemy needs postgresql+psycopg://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

# Ephemeral fallback is fine for dev; production must set SECRET_KEY (render.yaml generates one)
SECRET_KEY = os.getenv("SECRET_KEY") or secrets.token_hex(32)
JWT_ALGORITHM = "HS256"
JWT_TTL_HOURS = int(os.getenv("JWT_TTL_HOURS", "24") or "24")

# Streaks and daily quest resets follow East Africa Time
UTC_OFFSET_HOURS = 3

# Default campus (used by seed + /api/map/config); override per deployment
CAMPUS_NAME = os.getenv("CAMPUS_NAME", "Demo Campus (University of Nairobi)")
CAMPUS_LAT = float(os.getenv("CAMPUS_LAT", "-1.2795"))
CAMPUS_LNG = float(os.getenv("CAMPUS_LNG", "36.8163"))
