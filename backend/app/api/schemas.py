from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class TenantCreate(StrictModel):
    slug: str = Field(min_length=2, max_length=80, pattern=r"^[a-z0-9][a-z0-9-]*$")
    name: str = Field(min_length=2, max_length=150)
    path: str = Field(min_length=1, max_length=30)


class ProductCreate(StrictModel):
    name: str = Field(min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=5000)
    category: str | None = Field(default=None, max_length=100)


class PlanCreate(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    price: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    duration_days: int = Field(gt=0, le=3650)
    quota_gb: int | None = Field(default=None, ge=0, le=10000000)
    discount_kind: str = Field(default="none", pattern=r"^(none|fixed|percent)$")
    discount_value: Decimal = Field(default=Decimal("0"), ge=0, max_digits=18, decimal_places=2)


class OrderCreate(StrictModel):
    plan_id: int = Field(gt=0)
    idempotency_key: str = Field(min_length=8, max_length=100)


class PaymentCreate(StrictModel):
    order_id: int = Field(gt=0)
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    provider: str = Field(default="manual", min_length=2, max_length=40)
    idempotency_key: str = Field(min_length=8, max_length=100)


class WalletPost(StrictModel):
    user_id: int = Field(gt=0)
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    direction: str = Field(pattern=r"^(credit|debit)$")
    reason: str = Field(min_length=1, max_length=80)
    idempotency_key: str = Field(min_length=8, max_length=120)


class CouponCalc(StrictModel):
    code: str = Field(min_length=1, max_length=60)
    total: Decimal = Field(ge=0, max_digits=18, decimal_places=2)


class TicketCreate(StrictModel):
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=10000)


class ApprovalAction(StrictModel):
    approved: bool
    note: str | None = Field(default=None, max_length=2000)
