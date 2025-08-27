from datetime import datetime
from typing import Optional, List
import sys
from enum import Enum, auto

# ✔️ پشتیبانی از StrEnum در Python 3.10
if sys.version_info >= (3, 11):
    from enum import StrEnum
else:
    class StrEnum(str, Enum):
        pass

from sqlalchemy import (
    String, DateTime, Boolean,
    ForeignKey, Index, func,
    Enum as SqlEnum
)
from sqlalchemy.orm import (
    DeclarativeBase, Mapped,
    mapped_column, relationship
)

# ─────────────────────────────────────
# 🧱 Declarative Base
# ─────────────────────────────────────
class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""
    pass


# ─────────────────────────────────────
# 🚦 Enum: Task Priority
# ─────────────────────────────────────
class TaskPriority(StrEnum):
    """Priority levels for a Task."""
    HIGH = auto()
    MEDIUM = auto()
    LOW = auto()


# ─────────────────────────────────────
# 👤 User Model
# ─────────────────────────────────────
class User(Base):
    """
    Represents a Telegram user.
    """
    __tablename__ = "users"
    __table_args__ = (
        Index("idx_users_telegram_id", "telegram_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(unique=True, nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(100))
    username: Mapped[Optional[str]] = mapped_column(String(50))
    language: Mapped[str] = mapped_column(String(10), default="fa", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # 🔗 Relation to tasks
    tasks: Mapped[List["Task"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return (
            f"<User(id={self.id}, telegram_id={self.telegram_id}, "
            f"username='{self.username}', full_name='{self.full_name}')>"
        )


# ─────────────────────────────────────
# ✅ Task Model
# ─────────────────────────────────────
class Task(Base):
    """
    Represents a task created by a user.
    """
    __tablename__ = "tasks"
    __table_args__ = (
        Index("idx_tasks_user_status", "user_id", "is_done"),
        Index("idx_tasks_due_date", "due_date"),
        Index("idx_tasks_priority", "priority"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    content: Mapped[str] = mapped_column(String(255), nullable=False)
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # 🎯 Priority Enum
    priority: Mapped[TaskPriority] = mapped_column(
        SqlEnum(
            TaskPriority,
            name="task_priority_enum",
            validate_strings=True
        ),
        default=TaskPriority.MEDIUM,
        nullable=False
    )

    is_done: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    done_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    user: Mapped["User"] = relationship(
        back_populates="tasks",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        content_preview = self.content[:20] + "..." if self.content else "❓"
        return (
            f"<Task(id={self.id}, user_id={self.user_id}, "
            f"priority='{self.priority}', status={'✅' if self.is_done else '⏳'}, "
            f"due_date={self.due_date}, content='{content_preview}')>"
        )
