from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import OrderStatus


class OrderCreate(BaseModel):
    product_id: str = Field(min_length=1, max_length=36)
    quantity: int = Field(ge=1)
    unit_price: float = Field(gt=0)


class OrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: str
    product_id: str
    quantity: int
    unit_price: float
    status: OrderStatus
    created_at: datetime
    updated_at: datetime


class OrderUpdate(BaseModel):
    status: OrderStatus
