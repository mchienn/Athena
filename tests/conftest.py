import os

os.environ.setdefault(
    "JWT_SECRET_KEY",
    "test-only-jwt-secret-key-that-is-longer-than-32-characters",
)
