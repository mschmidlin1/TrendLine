from psycopg.rows import TupleRow
from src.base.singleton import SingletonMeta
from contextlib import contextmanager
from typing import Any, Iterator, List, Optional, Sequence
import psycopg
from psycopg import sql

from src.configs import (
    POSTGRES_DB,
    POSTGRES_HOST,
    POSTGRES_PASSWORD,
    POSTGRES_PORT,
    POSTGRES_USER,
)
from src.configs import RSS_FEED_URLS


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
    
    def init_news_sources_table(self) -> None:

        query = sql.SQL("""INSERT INTO news_sources (name, url)
        VALUES (%s, %s)
        ON CONFLICT (url) DO UPDATE
        SET name = EXCLUDED.name, updated_at = now()""").format(
            (RSS_FEED_URLS.keys(), RSS_FEED_URLS.values())
        )
        conn = self._require_conn()
        conn.execute(query)
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