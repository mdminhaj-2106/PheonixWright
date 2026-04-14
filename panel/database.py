import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base, Mapped, mapped_column
from sqlalchemy import String, Integer, DateTime, select
from datetime import datetime

DB_PATH = "sqlite+aiosqlite:///panel/pheonix_wright.db"

engine = create_async_engine(DB_PATH, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String, nullable=False, default='changeme123')
    license: Mapped[str] = mapped_column(String, nullable=False, default='none')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Seed data
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User))
        if not result.scalars().first():
            session.add_all([
                User(name='Alice Johnson', email='alice@corp.com', license='microsoft365'),
                User(name='Bob Smith', email='bob@corp.com', license='none'),
                User(name='Carol White', email='carol@corp.com', license='google-workspace')
            ])
            await session.commit()

async def reset_db():
    """Wipe and re-seed. Call before every demo recording."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    
    async with AsyncSessionLocal() as session:
        session.add_all([
            User(name='Alice Johnson', email='alice@corp.com', license='microsoft365'),
            User(name='Bob Smith', email='bob@corp.com', license='none'),
            User(name='Carol White', email='carol@corp.com', license='google-workspace')
        ])
        await session.commit()
