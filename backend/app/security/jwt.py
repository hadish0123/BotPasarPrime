from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt

from app.core.config import settings


def create_token(subject, claims=None):
    p = {"sub": str(subject), "exp": datetime.now(UTC) + timedelta(hours=12)}
    p.update(claims or {})
    return jwt.encode(p, settings.jwt_secret, algorithm="HS256")


def decode_token(token):
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except JWTError:
        raise ValueError("invalid token") from None
