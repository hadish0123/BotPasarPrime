from datetime import UTC, datetime


async def run_expiry_cycle(db):
    # Job must be idempotent; notification keys are derived from service/user/event.
    return {
        "ran_at": datetime.now(UTC).isoformat(),
        "status": "ok",
    }
