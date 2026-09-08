from sqlalchemy import select

from app.models.entities import Product


class ProductRepository:
    def __init__(self, s):
        self.s = s

    async def list(self):
        return list(
            (
                await self.s.scalars(
                    select(Product).where(
                        Product.tenant_id
                        == __import__("app.core.tenant", fromlist=["get_tenant"]).get_tenant()
                    )
                )
            ).all()
        )
