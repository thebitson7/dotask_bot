from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Column,
    String,
    DateTime,
    Boolean,
    ForeignKey,
    Index,
    func
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship
)


# 🧱 Base declarative class
class Base(DeclarativeBase):
    """Base class for all models."""
    pass


# 👤 User Model
class User(Base):
    """کاربر ثبت شده در ربات تلگرام"""
    __tablename__ = "users"
    __table_args__ = (
        Index("idx_users_telegram_id", "telegram_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    telegram_id: Mapped[int] = mapped_column(unique=True, nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(100))
    username: Mapped[Optional[str]] = mapped_column(String(50))
    language: Mapped[str] = mapped_column(String(10), default="fa")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # ارتباط با تسک‌ها
    tasks: Mapped[List["Task"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return (
            f"<User(id={self.id}, telegram_id={self.telegram_id}, "
            f"username={self.username}, language={self.language})>"
        )


# ✅ Task Model
class Task(Base):
    """وظیفه (تسک) ثبت‌شده توسط کاربر"""
    __tablename__ = "tasks"
    __table_args__ = (
        Index("idx_tasks_user_status", "user_id", "is_done"),
        Index("idx_tasks_due_date", "due_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    content: Mapped[str] = mapped_column(String(255), nullable=False)
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    is_done: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    done_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # ارتباط با کاربر
    user: Mapped["User"] = relationship(
        back_populates="tasks",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return (
            f"<Task(id={self.id}, user_id={self.user_id}, content='{self.content[:20]}...', "
            f"is_done={self.is_done}, due_date={self.due_date})>"
        )
