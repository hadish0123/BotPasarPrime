from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt

from app.core.config import settings

ALGORITHM = "HS256"
ISSUER = "3xshop"
AUDIENCE = "3xshop-api"
TOKEN_TYPE = "access"


def create_token(subject, claims=None, expires_hours=12):
    now = datetime.now(UTC)
    payload = {
        "sub": str(subject),
        "iat": now,
        "exp": now + timedelta(hours=expires_hours),
        "iss": ISSUER,
        "aud": AUDIENCE,
        "typ": TOKEN_TYPE,
    }
    payload.update(claims or {})
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def decode_token(token):
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[ALGORITHM],
            issuer=ISSUER,
            audience=AUDIENCE,
            options={"require_exp": True, "require_iat": True, "require_sub": True},
        )
    except JWTError:
        raise ValueError("invalid token") from None
    if payload.get("typ") != TOKEN_TYPE:
        raise ValueError("invalid token")
    return payload
