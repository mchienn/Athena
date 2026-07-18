import os

from dotenv import load_dotenv

load_dotenv()


def _load_jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET_KEY", "").strip()
    if len(secret) < 32:
        raise RuntimeError("JWT_SECRET_KEY must be configured with at least 32 characters.")
    return secret


# JWT Configuration
JWT_SECRET_KEY = _load_jwt_secret()
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256").strip()
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "30"))
REFRESH_COOKIE_SECURE = os.getenv("REFRESH_COOKIE_SECURE", "false").strip().lower() == "true"
REFRESH_COOKIE_SAMESITE = os.getenv("REFRESH_COOKIE_SAMESITE", "lax").strip().lower()
if REFRESH_COOKIE_SAMESITE not in {"lax", "strict", "none"}:
    raise RuntimeError("REFRESH_COOKIE_SAMESITE must be one of: lax, strict, none.")
if REFRESH_COOKIE_SAMESITE == "none" and not REFRESH_COOKIE_SECURE:
    raise RuntimeError("REFRESH_COOKIE_SECURE must be true when SameSite is none.")
