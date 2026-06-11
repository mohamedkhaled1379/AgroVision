#!/usr/bin/env python
"""Copy data from SQLite (agro_users.db) into Microsoft SQL Server."""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.chdir(ROOT)

from database import (  # noqa: E402
    DATABASE_PATH,
    get_db_connection,
    init_db,
    is_mssql,
)


TABLES = [
    "users",
    "site_settings",
    "history",
    "posts",
    "messages",
    "friendships",
    "friend_requests",
    "post_likes",
    "post_replies",
    "post_reactions",
    "iot_readings",
    "analysis_bookings",
]


def _sqlite_rows(table: str):
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(f"SELECT * FROM {table}").fetchall()
    conn.close()
    return rows


def _insert_rows(table: str, rows) -> int:
    if not rows:
        return 0

    columns = rows[0].keys()
    col_sql = ", ".join(columns)
    placeholders = ", ".join("?" for _ in columns)
    sql = f"INSERT INTO {table} ({col_sql}) VALUES ({placeholders})"

    conn = get_db_connection()
    count = 0
    identity_tables = {
        "users",
        "history",
        "posts",
        "messages",
        "friendships",
        "friend_requests",
        "post_likes",
        "post_replies",
        "post_reactions",
        "iot_readings",
        "analysis_bookings",
    }

    if table in identity_tables:
        conn.execute(f"SET IDENTITY_INSERT {table} ON")

    for row in rows:
        conn.execute(sql, tuple(row[c] for c in columns))
        count += 1

    if table in identity_tables:
        conn.execute(f"SET IDENTITY_INSERT {table} OFF")

    conn.commit()
    conn.close()
    return count


def migrate(*, reset_target: bool = False) -> None:
    if not is_mssql():
        raise SystemExit("Set DB_BACKEND=mssql and MSSQL_* variables before running migration.")

    if not os.path.exists(DATABASE_PATH):
        raise SystemExit(f"SQLite file not found: {DATABASE_PATH}")

    if reset_target:
        conn = get_db_connection()
        for script_name in ("mssql_reset.sql", "mssql_schema.sql"):
            schema_path = os.path.join(ROOT, "sql", script_name)
            with open(schema_path, "r", encoding="utf-8") as handle:
                for batch in handle.read().split("GO"):
                    batch = batch.strip()
                    if batch:
                        conn.execute(batch)
        conn.commit()
        conn.close()
    else:
        init_db()

    print(f"Migrating from {DATABASE_PATH} to SQL Server ({os.getenv('MSSQL_DATABASE', 'AgroVision')})...")
    for table in TABLES:
        rows = _sqlite_rows(table)
        inserted = _insert_rows(table, rows)
        print(f"  {table}: {inserted} rows")

    print("Migration complete.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate AgroVision SQLite data to SQL Server.")
    parser.add_argument(
        "--reset-target",
        action="store_true",
        help="Drop and recreate SQL Server tables before importing (destructive).",
    )
    args = parser.parse_args()
    migrate(reset_target=args.reset_target)


if __name__ == "__main__":
    main()
