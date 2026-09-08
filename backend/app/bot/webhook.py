from fastapi import APIRouter, Header, HTTPException

r = APIRouter(prefix="/webhooks", tags=["telegram"])


@r.post("/telegram/{tenant_id}")
async def telegram(
    tenant_id: int, update: dict, x_telegram_bot_api_secret_token: str | None = Header(default=None)
):
    from app.core.config import settings

    if x_telegram_bot_api_secret_token != settings.telegram_webhook_secret:
        raise HTTPException(401, "invalid webhook secret")
    return {"ok": True, "tenant_id": tenant_id}
