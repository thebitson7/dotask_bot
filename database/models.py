# database/models.py

from datetime import datetime
from typing import Optional, List

from sqlalchemy import (
    String, DateTime, Boolean, ForeignKey,
    Index, func
)
from sqlalchemy.orm import (
    DeclarativeBase, Mapped,
    mapped_column, relationship
)


# ─────────────────────────────
# 🧱 Declarative Base
# ─────────────────────────────
class Base(DeclarativeBase):
    """Base class for all models."""
    pass


# ─────────────────────────────
# 👤 User Model
# ─────────────────────────────
class User(Base):
    """
    Represents a registered Telegram user.
    """
    __tablename__ = "users"
    __table_args__ = (
        Index("idx_users_telegram_id", "telegram_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(unique=True, nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(100))
    username: Mapped[Optional[str]] = mapped_column(String(50))
    language: Mapped[str] = mapped_column(String(10), default="fa")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # 🔗 ارتباط با تسک‌ها
    tasks: Mapped[List["Task"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, tg={self.telegram_id}, username={self.username})>"


# ─────────────────────────────
# ✅ Task Model
# ─────────────────────────────
class Task(Base):
    """
    Represents a task created by a user.
    """
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

    # 🔗 ارتباط با کاربر
    user: Mapped["User"] = relationship(
        back_populates="tasks",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        status = "✅" if self.is_done else "⏳"
        return (
            f"<Task(id={self.id}, user={self.user_id}, "
            f"status={status}, due={self.due_date}, content='{self.content[:20]}')>"
        )
