from __future__ import annotations

from contextlib import contextmanager
from functools import lru_cache
import os
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import DATABASE_URL


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    connect_args = {}
    if DATABASE_URL.startswith("postgresql+"):
        connect_args["connect_timeout"] = int(
            os.getenv("DB_CONNECT_TIMEOUT_SECONDS", "3")
        )
    return create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        future=True,
        connect_args=connect_args,
    )


@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(
        bind=get_engine(),
        autoflush=False,
        expire_on_commit=False,
        future=True,
    )


@contextmanager
def session_scope() -> Iterator[Session]:
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
