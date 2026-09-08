from sqlalchemy import select

from app.core.tenant import get_tenant


class TenantRepository:
    model = None

    def __init__(self, session):
        self.session = session

    def scoped(self):
        return select(self.model).where(self.model.tenant_id == get_tenant())
