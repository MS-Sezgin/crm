"""The Database class: one place that owns the PostgreSQL connection.

Repositories never talk to psycopg2 directly, they call the methods of this class.

Every call commits by itself, unless it runs inside ``with db.transaction():``. In
that case everything is committed together at the end, or rolled back together if
anything fails (the data migration uses this).
"""
import os
from contextlib import contextmanager

try:
    import psycopg2
except ImportError as error:  # pragma: no cover - only without the library
    raise ImportError("psycopg2 is missing. Run: pip install -r requirements.txt") from error


class DatabaseError(Exception):
    """A database problem with a short, readable message."""


def _short_message(error):
    text = str(error).strip()
    return text.splitlines()[0] if text else error.__class__.__name__


class Database:
    def __init__(self, config):
        self.config = config
        self._connection = None
        self._depth = 0  # > 0 while inside transaction()

    def connect(self):
        if self._connection is not None and not self._connection.closed:
            return
        try:
            self._connection = psycopg2.connect(**self.config.connect_kwargs())
        except psycopg2.Error as error:
            raise DatabaseError(
                f"Could not connect to PostgreSQL ({self.config.host}:{self.config.port}, "
                f"database '{self.config.dbname}'): {_short_message(error)}") from error

    def close(self):
        if self._connection is not None and not self._connection.closed:
            self._connection.close()
        self._connection = None
        self._depth = 0

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *_exc):
        self.close()

    @contextmanager
    def transaction(self):
        """Group several statements: all succeed together or none of them stay."""
        self.connect()
        self._depth += 1
        try:
            yield self
        except BaseException:
            self._depth -= 1
            if self._depth == 0:
                self._connection.rollback()
            raise
        else:
            self._depth -= 1
            if self._depth == 0:
                self._connection.commit()

    def _run(self, sql, params, fetch):
        self.connect()
        try:
            with self._connection.cursor() as cursor:
                cursor.execute(sql, params)
                if fetch == "all":
                    result = cursor.fetchall()
                elif fetch == "one":
                    result = cursor.fetchone()
                else:
                    result = cursor.rowcount
            if self._depth == 0:
                self._connection.commit()
            return result
        except psycopg2.Error as error:
            if self._connection.closed:
                self._connection = None   # the server dropped us: the next call reconnects
                self._depth = 0
            elif self._depth == 0:
                self._connection.rollback()
            raise DatabaseError(_short_message(error)) from error

    def execute(self, sql, params=None):
        """Run INSERT / UPDATE / DELETE. Returns the number of affected rows."""
        return self._run(sql, params, None)

    def fetch_all(self, sql, params=None):
        """Return all rows as a list of tuples."""
        return self._run(sql, params, "all")

    def fetch_one(self, sql, params=None):
        """Return the first row as a tuple, or None."""
        return self._run(sql, params, "one")

    def fetch_value(self, sql, params=None):
        """Return the first column of the first row, or None."""
        row = self.fetch_one(sql, params)
        return row[0] if row else None

    def table_exists(self, name):
        return bool(self.fetch_value("SELECT to_regclass(%s) IS NOT NULL", (name,)))

    def execute_script(self, path):
        """Run a whole .sql file (for example database/schema.sql)."""
        if not os.path.exists(path):
            raise DatabaseError(f"SQL file not found: {path}")
        with open(path, encoding="utf-8") as handle:
            script = handle.read()
        self._run(script, None, None)  # params=None: '%' in the script is left alone
