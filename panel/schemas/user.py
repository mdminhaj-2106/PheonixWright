from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Integer, DateTime
from datetime import datetime
from panel.database import Base

class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String, nullable=False, default='changeme123')
    license: Mapped[str] = mapped_column(String, nullable=False, default='none')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
