from datetime import UTC, datetime, timedelta
from uuid import uuid4

import bcrypt
import jwt

from .config import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    JWT_ALGORITHM,
    JWT_SECRET_KEY,
    REFRESH_TOKEN_EXPIRE_DAYS,
)


class AuthService:
    _IDENTITY_CLAIMS = ("user_id", "patient_id", "phone")

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using bcrypt."""
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
        return hashed.decode("utf-8")

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a plain password against its bcrypt hash."""
        return bcrypt.checkpw(
            plain_password.encode("utf-8"), 
            hashed_password.encode("utf-8")
        )

    @staticmethod
    def create_access_token(data: dict) -> str:
        """Generate a JWT access token containing the payload and expiration time."""
        to_encode = data.copy()
        now = datetime.now(UTC)
        expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode.update({"iat": now, "exp": expire, "token_type": "access"})
        encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
        return encoded_jwt

    @staticmethod
    def create_refresh_token(
        data: dict,
        jti: str | None = None,
        session_id: str | None = None,
    ) -> str:
        """Generate a long-lived token used only to renew an access token."""
        to_encode = data.copy()
        now = datetime.now(UTC)
        expire = now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        to_encode.update(
            {
                "iat": now,
                "exp": expire,
                "jti": jti or str(uuid4()),
                "sid": session_id or str(uuid4()),
                "token_type": "refresh",
            }
        )
        return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

    @classmethod
    def _has_valid_identity(cls, payload: dict) -> bool:
        return all(
            isinstance(payload.get(claim), str) and bool(payload[claim].strip())
            for claim in cls._IDENTITY_CLAIMS
        )

    @staticmethod
    def decode_access_token(token: str) -> dict | None:
        """Decode and validate a JWT access token."""
        try:
            payload = jwt.decode(
                token,
                JWT_SECRET_KEY,
                algorithms=[JWT_ALGORITHM],
                options={"require": ["exp", "iat", "token_type", *AuthService._IDENTITY_CLAIMS]},
            )
            if (
                payload.get("token_type") != "access"
                or not AuthService._has_valid_identity(payload)
            ):
                return None
            return payload
        except jwt.PyJWTError:
            return None

    @staticmethod
    def decode_refresh_token(token: str) -> dict | None:
        """Decode a refresh token without accepting an access token in its place."""
        try:
            payload = jwt.decode(
                token,
                JWT_SECRET_KEY,
                algorithms=[JWT_ALGORITHM],
                options={
                    "require": [
                        "exp",
                        "iat",
                        "jti",
                        "sid",
                        "token_type",
                        *AuthService._IDENTITY_CLAIMS,
                    ]
                },
            )
            if payload.get("token_type") != "refresh":
                return None
            if not isinstance(payload.get("jti"), str) or not payload["jti"].strip():
                return None
            if not isinstance(payload.get("sid"), str) or not payload["sid"].strip():
                return None
            return payload if AuthService._has_valid_identity(payload) else None
        except jwt.PyJWTError:
            return None
