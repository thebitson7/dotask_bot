# database/db.py
"""
Compatibility shim to avoid duplication with `database/session.py`.

This module re-exports the canonical Engine/Session utilities from
`database.session` so existing imports keep working:

    from database.db import get_session, init_db
"""

from __future__ import annotations

import logging
from functools import lru_cache

# Re-export canonical APIs from the single source of truth
from database.session import (  # noqa: F401
    AsyncSessionFactory,
    engine,
    get_session,
    transactional_session,
    init_db,
    shutdown_db,
)

__all__ = [
    "engine",
    "AsyncSessionFactory",
    "get_session",
    "transactional_session",
    "init_db",
    "shutdown_db",
]


@lru_cache(maxsize=1)
def _warn_once() -> None:
    logging.getLogger(__name__).warning(
        "⚠️ `database.db` is deprecated. Use `database.session` instead. "
        "This module is a compatibility shim and will be removed in a future release."
    )


# Emit deprecation warning once on import
_warn_once()
