from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.auth.dependencies import get_current_user, role_required
from app.db.session import get_db
from app.models.user import Role, User

router = APIRouter(prefix="/admin", tags=["Admin"])


class UserResponse(BaseModel):
    id:        int
    email:     str
    role:      Role
    is_active: bool

    model_config = {"from_attributes": True}


class UpdateUserRequest(BaseModel):
    role:      Optional[Role] = None
    is_active: Optional[bool] = None


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(role_required(Role.admin)),
):
    result = await db.execute(select(User).order_by(User.id))
    return result.scalars().all()


@router.patch("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    body: UpdateUserRequest,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(role_required(Role.admin)),
):
    if user_id == current_admin.id:
        raise HTTPException(status_code=400, detail="Нельзя изменить собственный аккаунт")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    if body.role is None and body.is_active is None:
        raise HTTPException(status_code=400, detail="Укажите хотя бы одно поле для обновления")

    if body.role is not None:
        user.role = body.role
    if body.is_active is not None:
        user.is_active = body.is_active

    await db.commit()
    await db.refresh(user)
    return user
