from app.security.jwt import create_token


def issue_user_token(user_id, tenant_id, permissions):
    return create_token(user_id, {"tenant_id": tenant_id, "permissions": list(permissions)})
