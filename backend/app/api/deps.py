from fastapi import Header, HTTPException

from app.security.jwt import decode_token


def bearer(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "authentication required")
    try:
        return decode_token(authorization[7:])
    except ValueError:
        raise HTTPException(401, "invalid token") from None


def tenant_context(claims=bearer()):
    tenant_id = claims.get("tenant_id")
    is_platform_owner = bool(claims.get("is_platform_owner"))
    if tenant_id is None and not is_platform_owner:
        raise HTTPException(403, "tenant context required")
    return claims


def require_permission(permission: str):
    def dep(claims=tenant_context()):
        if permission not in claims.get("permissions", []):
            raise HTTPException(403, "forbidden")
        return claims

    return dep


def require_tenant_match(tenant_id: int, claims: dict) -> None:
    if claims.get("is_platform_owner"):
        return
    claim_tenant = claims.get("tenant_id")
    if claim_tenant is None or int(claim_tenant) != int(tenant_id):
        raise HTTPException(403, "cross-tenant access denied")
