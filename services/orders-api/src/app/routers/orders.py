from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Order
from app.schemas import OrderCreate, OrderRead, OrderUpdate

router = APIRouter(prefix="/orders", tags=["orders"])
logger: structlog.stdlib.BoundLogger = structlog.get_logger()


def _require_user(x_user_id: Annotated[str | None, Header()] = None) -> str:
    if not x_user_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing X-User-Id header")
    return x_user_id


CurrentUser = Annotated[str, Depends(_require_user)]


@router.post("", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
async def create_order(
    payload: OrderCreate,
    user_id: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> Order:
    order = Order(user_id=user_id, **payload.model_dump())
    session.add(order)
    await session.commit()
    await session.refresh(order)
    logger.info("order.created", order_id=order.id, user_id=order.user_id)
    return order


@router.get("", response_model=list[OrderRead])
async def list_orders(
    user_id: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> list[Order]:
    result = await session.execute(
        select(Order).where(Order.user_id == user_id).order_by(Order.created_at.desc())
    )
    return list(result.scalars().all())


@router.get("/{order_id}", response_model=OrderRead)
async def get_order(
    order_id: int,
    user_id: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> Order:
    result = await session.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if order is None or order.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return order


@router.patch("/{order_id}", response_model=OrderRead)
async def update_order_status(
    order_id: int,
    payload: OrderUpdate,
    user_id: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> Order:
    result = await session.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if order is None or order.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    order.status = payload.status
    await session.commit()
    await session.refresh(order)
    logger.info("order.status_updated", order_id=order.id, status=order.status)
    return order
