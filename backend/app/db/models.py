from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(320), unique=True, nullable=True, index=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    password_salt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    post: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    district: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    thana: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)


class AuthSession(Base):
    __tablename__ = "sessions"

    token: Mapped[str] = mapped_column(String(255), primary_key=True)
    username: Mapped[str] = mapped_column(
        String(255), ForeignKey("users.username", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, index=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, index=True)


class Case(Base):
    __tablename__ = "cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    created_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    saved_searches: Mapped[list["SavedSearch"]] = relationship(
        back_populates="case", cascade="all, delete-orphan", passive_deletes=True
    )


class SavedSearch(Base):
    __tablename__ = "saved_searches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    criteria_json: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    case: Mapped[Case] = relationship(back_populates="saved_searches")


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("cases.id", ondelete="SET NULL"), nullable=True, index=True
    )
    job_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    payload_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    worker_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    claim_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True, index=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True)
    result_uri: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)


class AnalysisMetadata(Base):
    __tablename__ = "analysis_metadata"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("cases.id", ondelete="SET NULL"), nullable=True, index=True
    )
    job_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    analysis_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("cases.id", ondelete="SET NULL"), nullable=True, index=True
    )
    analysis_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("analysis_metadata.id", ondelete="SET NULL"), nullable=True, index=True
    )
    severity: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    alert_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    details_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, index=True)


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)


class UserRole(Base):
    __tablename__ = "user_roles"

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    role_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
    )


class CaseMembership(Base):
    __tablename__ = "case_memberships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)


class RefreshSession(Base):
    __tablename__ = "refresh_sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, index=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor_user_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    resource_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    outcome: Mapped[str] = mapped_column(String(20), nullable=False)
    request_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    source_ip: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, index=True)
