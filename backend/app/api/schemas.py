from pydantic import BaseModel, Field


class TenantCreate(BaseModel):
    slug: str = Field(min_length=2, max_length=80)
    name: str
    path: str


class ProductCreate(BaseModel):
    name: str
    description: str | None = None
    category: str | None = None


class PlanCreate(BaseModel):
    name: str
    price: float
    duration_days: int
    quota_gb: int | None = None
    discount_kind: str = "none"
    discount_value: float = 0


class OrderCreate(BaseModel):
    plan_id: int
    idempotency_key: str


class PaymentCreate(BaseModel):
    order_id: int
    amount: float
    provider: str = "manual"
    idempotency_key: str


class WalletPost(BaseModel):
    user_id: int
    amount: float
    direction: str
    reason: str
    idempotency_key: str


class CouponCalc(BaseModel):
    code: str
    total: float


class TicketCreate(BaseModel):
    subject: str
    body: str


class ApprovalAction(BaseModel):
    approved: bool
    note: str | None = None
