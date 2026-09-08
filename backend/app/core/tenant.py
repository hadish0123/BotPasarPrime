from contextvars import ContextVar

tenant_context: ContextVar[int | None] = ContextVar("tenant_id", default=None)


def set_tenant(tid):
    tenant_context.set(tid)


def get_tenant():
    tid = tenant_context.get()
    if tid is None:
        raise RuntimeError("tenant context required")
    return tid
