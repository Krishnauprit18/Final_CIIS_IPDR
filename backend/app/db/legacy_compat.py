from __future__ import annotations

from typing import Any, Iterable, Optional, Sequence

from app.db.repositories import verify_database_schema
from app.db.session import get_engine


class CompatRow:
    """Small sqlite3.Row-like wrapper for legacy handlers during Phase 2."""

    def __init__(self, columns: Sequence[str], values: Sequence[Any]) -> None:
        self._columns = list(columns)
        self._values = tuple(values)
        self._mapping = dict(zip(self._columns, self._values))

    def keys(self):
        return self._columns

    def __getitem__(self, key):
        if isinstance(key, str):
            return self._mapping[key]
        return self._values[key]

    def __iter__(self):
        return iter(self._values)

    def __len__(self):
        return len(self._values)


class LegacyCursor:
    def __init__(self, cursor: Any) -> None:
        self._cursor = cursor
        self._buffered_row: Optional[CompatRow] = None
        self.lastrowid: Optional[int] = None

    @property
    def description(self):
        return self._cursor.description

    def _columns(self) -> list[str]:
        if not self._cursor.description:
            return []
        return [column[0] for column in self._cursor.description]

    def _wrap(self, row: Any) -> Optional[CompatRow]:
        if row is None:
            return None
        return CompatRow(self._columns(), row)

    def execute(self, sql: str, params: Optional[Iterable[Any]] = None):
        normalized = sql.strip()
        driver_sql = sql.replace("?", "%s")
        lowered = normalized.lower()

        # SQLite exposed cursor.lastrowid. Preserve the single legacy use by
        # asking PostgreSQL to return the generated case id explicitly.
        capture_case_id = lowered.startswith("insert into cases") and "returning" not in lowered
        if capture_case_id:
            driver_sql = driver_sql.rstrip().rstrip(";") + " RETURNING id"

        self._cursor.execute(driver_sql, tuple(params or ()))

        if capture_case_id:
            row = self._cursor.fetchone()
            if row is not None:
                self.lastrowid = int(row[0])
        return self

    def fetchone(self):
        if self._buffered_row is not None:
            row = self._buffered_row
            self._buffered_row = None
            return row
        return self._wrap(self._cursor.fetchone())

    def fetchall(self):
        return [self._wrap(row) for row in self._cursor.fetchall()]

    def close(self) -> None:
        self._cursor.close()


class LegacyConnection:
    """DB-API compatibility facade backed by SQLAlchemy's PostgreSQL engine."""

    def __init__(self) -> None:
        self._connection = get_engine().raw_connection()
        # Some legacy code assigns sqlite3 row_factory. Keep the attribute as a
        # harmless compatibility no-op so those code paths do not care.
        self.row_factory = None

    def cursor(self) -> LegacyCursor:
        return LegacyCursor(self._connection.cursor())

    def commit(self) -> None:
        self._connection.commit()

    def rollback(self) -> None:
        self._connection.rollback()

    def close(self) -> None:
        self._connection.close()


def get_db_conn() -> LegacyConnection:
    return LegacyConnection()


def install_legacy_postgres_compat(legacy_handlers: Any) -> None:
    """Redirect Phase-1 legacy persistence globals to PostgreSQL.

    Phase 1 intentionally preserved handler bodies in one compatibility module.
    During Phase 2 we switch their runtime persistence boundary without changing
    the public API contract. Future phases can retire this adapter as handlers are
    moved to dedicated repositories/services.
    """

    legacy_handlers.get_db_conn = get_db_conn
    legacy_handlers.init_db = verify_database_schema
