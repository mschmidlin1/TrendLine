from psycopg.rows import TupleRow
from trend_core.base.singleton import SingletonMeta
from contextlib import contextmanager
from typing import Any, Iterator, List, Optional, Sequence
import psycopg
from psycopg import sql

from trend_core.configs import (
    POSTGRES_DB,
    POSTGRES_HOST,
    POSTGRES_PASSWORD,
    POSTGRES_PORT,
    POSTGRES_USER,
)
from trend_core.configs import RSS_FEED_URLS


class DatabaseService(metaclass=SingletonMeta):
    def __init__(self) -> None:
        self._conn: psycopg.Connection[TupleRow] | None = None

    def open(self):
        self._conn = psycopg.connect(
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            dbname=POSTGRES_DB,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
        )
    def close(self):
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def _require_conn(self) -> psycopg.Connection[TupleRow]:
        if self._conn is None:
            raise RuntimeError("Cannot perform action when _conn is None. Must call .open() first")

        #check if connection is live or needs to be restarted
        is_live = False
        try:
            self._conn.execute("SELECT 1")
            self._conn.rollback()
            is_live = True
        except psycopg.OperationalError:
            is_live = False

        
        if is_live:
            return self._conn
        try:
            #attempt to close connection
            self._conn.close()
        except Exception:
            pass
        self.open() #open fresh connection
        return self._conn
        

    def insert_row(self, table: str, columns: list[str], values: list, returning: str | None = None) -> int | None:
        if returning == "":
            raise ValueError("Don't be a jackass")
        if not columns or not values:
            raise ValueError("No data provided for SQL.")
        if len(columns) != len(values):
            raise ValueError("columns and values must be the same length")

        
        if returning is None:
            query = sql.SQL("INSERT INTO {table} ({fields}) VALUES ({placeholders})").format(
                table=sql.Identifier(table),
                fields=sql.SQL(", ").join(map(sql.Identifier, columns)),
                placeholders=sql.SQL(", ").join(sql.Placeholder() * len(values)),
            )
        else:
            query = sql.SQL("INSERT INTO {table} ({fields}) VALUES ({placeholders}) RETURNING {pk}").format(
                table=sql.Identifier(table),
                fields=sql.SQL(", ").join(map(sql.Identifier, columns)),
                placeholders=sql.SQL(", ").join(sql.Placeholder() * len(values)),
                pk=sql.Identifier(returning),
            )


        conn = self._require_conn()
        result = conn.execute(query, values)
        if returning is None:
            conn.commit()
            return None
        row = result.fetchone()
        conn.commit()
        if row is None:
            raise RuntimeError("INSERT ... RETURNING produced no row")
        return row[0]

    
    def insert_row_dict(self, table: str, row: dict, returning: str | None = None) -> int | None:
        columns = list(row.keys())
        values = list(row.values())
        return self.insert_row(table, columns, values, returning)
    
    def update_row_dict(self, table: str, row: dict, key: str) -> None:
        """UPDATE one row. `row` holds the new values; `row[key]` identifies the row."""
        if key not in row:
            raise ValueError(f"row must contain key column '{key}'")
        set_cols = [c for c in row if c != key]
        if not set_cols:
            raise ValueError("No columns to update.")

        query = sql.SQL("UPDATE {table} SET {sets} WHERE {key} = {key_ph}").format(
            table=sql.Identifier(table),
            sets=sql.SQL(", ").join(
                sql.SQL("{} = {}").format(sql.Identifier(c), sql.Placeholder())
                for c in set_cols
            ),
            key=sql.Identifier(key),
            key_ph=sql.Placeholder(),
        )
        values = [row[c] for c in set_cols] + [row[key]]

        conn = self._require_conn()
        conn.execute(query, values)
        conn.commit()

    def fetch_one(self, query, params=None):
        conn = self._require_conn()
        result = conn.execute(query, params)
        row = result.fetchone()
        conn.commit()
        return row
    def fetch_all(self, query, params=None):
        conn = self._require_conn()
        result = conn.execute(query, params)
        rows = result.fetchall()
        conn.commit()
        return rows

    def execute(self, query, params=None) -> None:
        conn = self._require_conn()
        conn.execute(query, params)
        conn.commit()