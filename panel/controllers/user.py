from sqlalchemy import select, or_
from sqlalchemy.exc import IntegrityError
from panel.database import AsyncSessionLocal
from panel.schemas.user import User

async def get_all_users(q: str = ""):
    async with AsyncSessionLocal() as session:
        stmt = select(User)
        if q:
            stmt = stmt.where(or_(User.name.icontains(q), User.email.icontains(q)))
        result = await session.execute(stmt)
        return result.scalars().all()

async def create_user_db(name: str, email: str, license: str):
    async with AsyncSessionLocal() as session:
        new_user = User(name=name, email=email, license=license)
        session.add(new_user)
        try:
            await session.commit()
            return new_user
        except IntegrityError:
            await session.rollback()
            return None

async def get_user_by_id(user_id: int):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        return result.scalars().first()

async def update_user_db(user_id: int, license: str, password: str = None):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalars().first()
        if user:
            user.license = license
            if password:
                user.password = password
            await session.commit()
            return user
        return None

async def delete_user_db(user_id: int):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalars().first()
        if user:
            await session.delete(user)
            await session.commit()
            return True
        return False
