from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer

from app.models import OrderStatus

Money = Annotated[
    Decimal,
    Field(gt=0, max_digits=10, decimal_places=2),
    PlainSerializer(lambda value: float(value), return_type=float, when_used="json"),
]


class OrderCreate(BaseModel):
    product_id: str = Field(min_length=1, max_length=36)
    quantity: int = Field(ge=1)
    unit_price: Money


class OrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: str
    product_id: str
    quantity: int
    unit_price: Money
    status: OrderStatus
    created_at: datetime
    updated_at: datetime


class OrderUpdate(BaseModel):
    status: OrderStatus
