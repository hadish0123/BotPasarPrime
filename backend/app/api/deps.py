from fastapi import Header, HTTPException

from app.security.jwt import decode_token


def bearer(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "authentication required")
    try:
        return decode_token(authorization[7:])
    except ValueError:
        raise HTTPException(401, "invalid token") from None


def require_permission(permission):
    def dep(claims=bearer()):
        if permission not in claims.get("permissions", []):
            raise HTTPException(403, "forbidden")
        return claims

    return dep
