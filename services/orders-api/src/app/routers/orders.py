import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Order
from app.schemas import OrderCreate, OrderRead, OrderUpdate

router = APIRouter(prefix="/orders", tags=["orders"])
logger: structlog.stdlib.BoundLogger = structlog.get_logger()


@router.post("", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
async def create_order(
    payload: OrderCreate,
    session: AsyncSession = Depends(get_session),
) -> Order:
    order = Order(**payload.model_dump())
    session.add(order)
    await session.commit()
    await session.refresh(order)
    logger.info("order.created", order_id=order.id, user_id=order.user_id)
    return order


@router.get("", response_model=list[OrderRead])
async def list_orders(
    user_id: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> list[Order]:
    q = select(Order).order_by(Order.created_at.desc())
    if user_id:
        q = q.where(Order.user_id == user_id)
    result = await session.execute(q)
    return list(result.scalars().all())


@router.get("/{order_id}", response_model=OrderRead)
async def get_order(
    order_id: int,
    session: AsyncSession = Depends(get_session),
) -> Order:
    result = await session.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return order


@router.patch("/{order_id}", response_model=OrderRead)
async def update_order_status(
    order_id: int,
    payload: OrderUpdate,
    session: AsyncSession = Depends(get_session),
) -> Order:
    result = await session.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    order.status = payload.status
    await session.commit()
    await session.refresh(order)
    logger.info("order.status_updated", order_id=order.id, status=order.status)
    return order
