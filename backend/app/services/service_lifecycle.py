from app.models.entities import Service


async def provision(db, tenant_id, user_id, external):
    service = Service(
        tenant_id=tenant_id,
        user_id=user_id,
        external_id=external.get("id"),
        status=external.get("status", "active"),
        metadata_json=external,
    )
    db.add(service)
    await db.flush()
    return service
