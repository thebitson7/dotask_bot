# database/models.py
from __future__ import annotations

import sys
from datetime import datetime
from typing import List, Optional

# ---- StrEnum compatibility (Py3.10+) ----
if sys.version_info >= (3, 11):
    from enum import StrEnum
else:
    from enum import Enum
    class StrEnum(str, Enum):  # type: ignore[no-redef]
        def __str__(self) -> str:
            return self.value

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Index,
    MetaData,
    String,
    func,
    and_,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.ext.hybrid import hybrid_property


# ─────────────────────────────────────
# 🧱 Declarative Base + naming conventions
# ─────────────────────────────────────
_naming = MetaData(
    naming_convention={
        "ix": "ix_%(table_name)s_%(column_0_name)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }
)

class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""
    metadata = _naming


# ─────────────────────────────────────
# 🚦 Enum: Task Priority
# ─────────────────────────────────────
class TaskPriority(StrEnum):
    """Priority levels for a Task."""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

    @classmethod
    def default(cls) -> "TaskPriority":
        return cls.MEDIUM


# ─────────────────────────────────────
# 👤 User Model
# ─────────────────────────────────────
class User(Base):
    """Represents a Telegram user."""
    __tablename__ = "users"
    __table_args__ = (
        Index("idx_users_telegram_id", "telegram_id"),
        {"comment": "Telegram users table"},
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(unique=True, nullable=False, comment="Telegram user id")
    full_name: Mapped[Optional[str]] = mapped_column(String(100), comment="Display/full name")
    username: Mapped[Optional[str]] = mapped_column(String(50), comment="Telegram @username")
    language: Mapped[str] = mapped_column(String(10), default="fa", nullable=False, comment="Preferred language")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),         # UTC در سمت DB
        nullable=False,
        comment="Creation timestamp (UTC)",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),               # به‌روزرسانی در ORM-side (cross-DB قابل اعتماد)
        nullable=False,
        comment="Last update timestamp (UTC)",
    )

    # 🔗 Relation to tasks
    tasks: Mapped[List["Task"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
        passive_deletes=True,
    )

    __mapper_args__ = {"eager_defaults": True}  # created_at/updated_at بعد از INSERT بدون refresh در دسترس‌اند

    def __repr__(self) -> str:
        return f"<User id={self.id} tg={self.telegram_id} username={self.username!r} name={self.full_name!r}>"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "telegram_id": self.telegram_id,
            "username": self.username,
            "full_name": self.full_name,
            "language": self.language,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


# ─────────────────────────────────────
# ✅ Task Model
# ─────────────────────────────────────
class Task(Base):
    """Represents a task created by a user."""
    __tablename__ = "tasks"
    __table_args__ = (
        # شاخص‌های پرکاربرد برای کوئری‌های لیست
        Index("idx_tasks_user_status", "user_id", "is_done"),
        Index("idx_tasks_user_created", "user_id", "created_at"),
        Index("idx_tasks_user_due", "user_id", "due_date"),
        Index("idx_tasks_priority", "priority"),
        # قیود کیفیت داده (cross-DB):
        CheckConstraint("length(content) >= 3", name="tasks_content_minlen"),
        CheckConstraint("(done_at IS NULL) OR (is_done = 1)", name="tasks_done_at_consistency"),
        {"comment": "Tasks created by users"},
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # ⚠️ این «id داخلی users» است، نه telegram_id
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Owner user id (internal users.id)",
    )

    content: Mapped[str] = mapped_column(String(255), nullable=False, comment="Task content (<=255 chars)")
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), comment="Optional due date (UTC)")

    # 🎯 Priority Enum (native PG enum؛ در بقیه DBها string-based)
    priority: Mapped[TaskPriority] = mapped_column(
        SqlEnum(TaskPriority, name="task_priority_enum", validate_strings=True),
        default=TaskPriority.default,
        nullable=False,
        comment="Task priority",
    )

    is_done: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, comment="Completion flag")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Creation timestamp (UTC)",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="Last update timestamp (UTC)",
    )
    done_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), comment="When marked done (UTC)")

    # 🔗 Relationship
    user: Mapped["User"] = relationship(
        back_populates="tasks",
        lazy="selectin",
        passive_deletes=True,
    )

    __mapper_args__ = {"eager_defaults": True}

    # ── Hybrid: Python-side + SQL expression (برای فیلتر DB-side) ─────────────
    @hybrid_property
    def overdue(self) -> bool:
        """
        True if task has a due_date in the past and is not done.
        """
        if self.is_done or self.due_date is None:
            return False
        now_aware = datetime.utcnow().astimezone(self.due_date.tzinfo)
        return self.due_date < now_aware

    @overdue.expression  # به DB می‌گوید چطور فیلتر کند؛ func.now() cross-DB
    def overdue(cls):
        return and_(cls.is_done.is_(False), cls.due_date.is_not(None), cls.due_date < func.now())

    @property
    def status(self) -> str:
        return "DONE" if self.is_done else "PENDING"

    def __repr__(self) -> str:
        content_preview = (self.content[:20] + "…") if self.content else "❓"
        return (
            f"<Task id={self.id} user_id={self.user_id} prio={self.priority} "
            f"status={'✅' if self.is_done else '⏳'} due={self.due_date} content={content_preview!r}>"
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "content": self.content,
            "priority": str(self.priority),
            "is_done": self.is_done,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "done_at": self.done_at.isoformat() if self.done_at else None,
        }
