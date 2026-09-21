#!/usr/bin/env python3
"""Apply sql/schema.sql to Postgres and seed news_sources from RSS_FEED_URLS."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import LiteralString, cast
import psycopg
from dotenv import load_dotenv

# Project root = parent of scripts/
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))  # so "import src..." works when run as a script

load_dotenv(ROOT / ".env", override=False)

from src.lib.configs import (  # noqa: E402
    POSTGRES_DB,
    POSTGRES_HOST,
    POSTGRES_PASSWORD,
    POSTGRES_PORT,
    POSTGRES_USER,
    RSS_FEED_URLS,
)


def main() -> None:
    schema_path = ROOT / "sql" / "schema.sql"
    if not schema_path.is_file():
        raise FileNotFoundError(f"Missing schema file: {schema_path}")

    schema_sql = schema_path.read_text(encoding="utf-8")

    conninfo = (
        f"host={POSTGRES_HOST} "
        f"port={POSTGRES_PORT} "
        f"dbname={POSTGRES_DB} "
        f"user={POSTGRES_USER} "
        f"password={POSTGRES_PASSWORD}"
    )

    print(f"Connecting to {POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB} as {POSTGRES_USER} ...")

    # autocommit=True so DDL in the script applies cleanly
    with psycopg.connect(conninfo, autocommit=True) as conn:
        print(f"Applying {schema_path} ...")
        conn.execute(cast(LiteralString, schema_sql))
        print("Schema applied.")

        print("Seeding news_sources from RSS_FEED_URLS ...")
        for name, url in RSS_FEED_URLS.items():
            conn.execute(
                """
                INSERT INTO news_sources (name, url)
                VALUES (%s, %s)
                ON CONFLICT (url) DO UPDATE
                  SET name = EXCLUDED.name,
                      updated_at = now()
                """,
                (name, url),
            )
        print(f"Seeded/updated {len(RSS_FEED_URLS)} feed(s).")

    print("Done.")


if __name__ == "__main__":
    main()