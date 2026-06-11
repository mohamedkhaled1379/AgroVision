"""Database access for AgroVision — SQLite (default) or Microsoft SQL Server."""

from __future__ import annotations

import datetime
import os
import re
import sqlite3
from typing import Any

try:
    import pyodbc
except ImportError:  # pragma: no cover
    pyodbc = None


def _load_env_file() -> None:
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path, encoding="utf-8") as handle:
        for raw in handle:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env_file()

DATABASE_PATH = os.getenv("DATABASE_PATH", "agro_users.db")
DB_BACKEND = os.getenv("DB_BACKEND", "sqlite").strip().lower()

MSSQL_SERVER = os.getenv("MSSQL_SERVER", r"localhost\SQLEXPRESS").strip()
MSSQL_DATABASE = os.getenv("MSSQL_DATABASE", "AgroVision").strip()
MSSQL_USER = os.getenv("MSSQL_USER", "sa").strip()
MSSQL_PASSWORD = os.getenv("MSSQL_PASSWORD", "").strip()
MSSQL_DRIVER = os.getenv("MSSQL_DRIVER", "ODBC Driver 18 for SQL Server").strip()
MSSQL_TRUST_SERVER_CERTIFICATE = os.getenv("MSSQL_TRUST_SERVER_CERTIFICATE", "yes").strip().lower() in (
    "1",
    "true",
    "yes",
)
MSSQL_TRUSTED_CONNECTION = os.getenv("MSSQL_TRUSTED_CONNECTION", "").strip().lower() in (
    "1",
    "true",
    "yes",
)


def _use_windows_auth() -> bool:
    if MSSQL_TRUSTED_CONNECTION:
        return True
    if not MSSQL_PASSWORD:
        return True
    return False


def is_mssql() -> bool:
    return DB_BACKEND in ("mssql", "sqlserver", "sql_server")


def is_sqlite() -> bool:
    return not is_mssql()


def is_integrity_error(exc: BaseException) -> bool:
    if isinstance(exc, sqlite3.IntegrityError):
        return True
    name = type(exc).__name__
    return name in ("IntegrityError", "IntegrityErrorException") or "2627" in str(exc) or "2601" in str(exc)


def _row_to_dict(cursor, row) -> dict[str, Any]:
    if row is None:
        return None
    columns = [col[0] for col in cursor.description]
    return {columns[i]: row[i] for i in range(len(columns))}


def _adapt_sql_for_mssql(sql: str) -> str:
    adapted = sql

    if re.search(r"\bINSERT\s+OR\s+IGNORE\b", adapted, re.IGNORECASE):
        match = re.search(
            r"INSERT\s+OR\s+IGNORE\s+INTO\s+(\w+)\s*\(([^)]+)\)\s*VALUES\s*\(([^)]+)\)",
            adapted,
            re.IGNORECASE | re.DOTALL,
        )
        if match:
            table, cols, placeholders = match.groups()
            if table.lower() == "friendships":
                adapted = f"""
                IF NOT EXISTS (SELECT 1 FROM friendships WHERE user1_id = ? AND user2_id = ?)
                INSERT INTO friendships ({cols}) VALUES ({placeholders})
                """
            else:
                adapted = re.sub(r"INSERT\s+OR\s+IGNORE", "INSERT", adapted, flags=re.IGNORECASE)

    adapted = re.sub(r"\bsubstr\s*\(", "SUBSTRING(", adapted, flags=re.IGNORECASE)

    adapted = re.sub(
        r"(\sORDER\s+BY\s+.+?)\s+LIMIT\s+\?\s*$",
        r"\1 OFFSET 0 ROWS FETCH NEXT ? ROWS ONLY",
        adapted,
        flags=re.IGNORECASE | re.DOTALL,
    )
    adapted = re.sub(
        r"(\sORDER\s+BY\s+.+?)\s+LIMIT\s+(\d+)\s*$",
        r"\1 OFFSET 0 ROWS FETCH NEXT \2 ROWS ONLY",
        adapted,
        flags=re.IGNORECASE | re.DOTALL,
    )

    if re.search(r"\sLIMIT\s+1\s*$", adapted, re.IGNORECASE):
        adapted = re.sub(r"\sLIMIT\s+1\s*$", "", adapted, flags=re.IGNORECASE)
        adapted = re.sub(r"(\bSELECT\b)", r"\1 TOP 1", adapted, count=1, flags=re.IGNORECASE)

    return adapted.strip()


def _adapt_params_for_mssql(sql: str, params: tuple | list) -> tuple:
    params = tuple(params or ())
    if "IF NOT EXISTS (SELECT 1 FROM friendships WHERE user1_id = ? AND user2_id = ?)" in sql:
        if len(params) >= 2:
            return (params[0], params[1]) + params
    return params


class CompatCursor:
    def __init__(self, cursor, conn_wrapper: "DBConnection", sql: str):
        self._cursor = cursor
        self._conn = conn_wrapper
        self._sql = sql
        self._lastrowid: int | None = None

    @property
    def lastrowid(self) -> int | None:
        if self._conn.backend == "sqlite":
            return self._cursor.lastrowid
        return self._lastrowid

    def fetchone(self):
        row = self._cursor.fetchone()
        return _row_to_dict(self._cursor, row)

    def fetchall(self):
        rows = self._cursor.fetchall()
        return [_row_to_dict(self._cursor, row) for row in rows]


class DBConnection:
    backend: str

    def __init__(self, conn, backend: str):
        self._conn = conn
        self.backend = backend

    def execute(self, sql: str, params: tuple | list = ()):
        params = tuple(params or ())
        if self.backend == "mssql":
            sql = _adapt_sql_for_mssql(sql)
            params = _adapt_params_for_mssql(sql, params)

        cursor = self._conn.cursor()
        cursor.execute(sql, params)
        compat = CompatCursor(cursor, self, sql)

        if self.backend == "mssql" and sql.strip().upper().startswith("INSERT"):
            id_cursor = self._conn.cursor()
            id_cursor.execute("SELECT CAST(SCOPE_IDENTITY() AS INT) AS id")
            id_row = id_cursor.fetchone()
            compat._lastrowid = int(id_row[0]) if id_row and id_row[0] is not None else None
            id_cursor.close()

        return compat

    def commit(self) -> None:
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def cursor(self):
        return self._conn.cursor()


def _mssql_connection_string(*, for_database: str | None = None) -> str:
    if pyodbc is None:
        raise RuntimeError("pyodbc is not installed. Run: pip install pyodbc")

    database = for_database or MSSQL_DATABASE
    parts = [
        f"DRIVER={{{MSSQL_DRIVER}}}",
        f"SERVER={MSSQL_SERVER}",
        f"DATABASE={database}",
    ]
    if _use_windows_auth():
        parts.append("Trusted_Connection=yes")
    else:
        parts.append(f"UID={MSSQL_USER}")
        parts.append(f"PWD={MSSQL_PASSWORD}")
    if MSSQL_TRUST_SERVER_CERTIFICATE:
        parts.append("TrustServerCertificate=yes")
    return ";".join(parts)


def ensure_mssql_database() -> None:
    if pyodbc is None:
        raise RuntimeError("pyodbc is not installed. Run: pip install pyodbc")
    conn = pyodbc.connect(_mssql_connection_string(for_database="master"), autocommit=True)
    conn.execute(
        f"IF DB_ID(N'{MSSQL_DATABASE}') IS NULL CREATE DATABASE [{MSSQL_DATABASE}]"
    )
    conn.close()


def get_db_connection() -> DBConnection:
    if is_mssql():
        if pyodbc is None:
            raise RuntimeError("DB_BACKEND=mssql but pyodbc is not installed.")
        conn = pyodbc.connect(_mssql_connection_string(), autocommit=False)
        return DBConnection(conn, "mssql")

    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return DBConnection(conn, "sqlite")


def get_table_columns(cur, table_name: str) -> list[str]:
    if is_mssql():
        rows = cur.execute(
            """
            SELECT COLUMN_NAME AS name
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = ?
            ORDER BY ORDINAL_POSITION
            """,
            (table_name,),
        ).fetchall()
        return [row["name"] for row in rows]

    rows = cur.execute(f"PRAGMA table_info({table_name})").fetchall()
    return [row["name"] for row in rows]


def table_exists(cur, table_name: str) -> bool:
    if is_mssql():
        row = cur.execute(
            "SELECT 1 AS ok FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = ?",
            (table_name,),
        ).fetchone()
        return row is not None
    row = cur.execute(
        "SELECT 1 AS ok FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _run_mssql_schema(cur) -> None:
    schema_path = os.path.join(os.path.dirname(__file__), "sql", "mssql_schema.sql")
    if not os.path.exists(schema_path):
        raise FileNotFoundError(f"Missing SQL Server schema: {schema_path}")

    with open(schema_path, "r", encoding="utf-8") as handle:
        content = handle.read()

    batches = [batch.strip() for batch in content.split("GO") if batch.strip()]
    for batch in batches:
        cur.execute(batch)


def _seed_default_users(cur) -> None:
    from werkzeug.security import generate_password_hash

    existing_admin = cur.execute(
        "SELECT id FROM users WHERE role = 'admin' LIMIT 1"
    ).fetchone()
    if not existing_admin:
        cur.execute(
            "INSERT INTO users (username, phone, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)",
            ("admin", "", generate_password_hash("admin123"), "admin", datetime.datetime.now().isoformat()),
        )

    existing_worker = cur.execute(
        "SELECT id FROM users WHERE username = 'worker' LIMIT 1"
    ).fetchone()
    if not existing_worker:
        cur.execute(
            "INSERT INTO users (username, phone, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)",
            ("worker", "", generate_password_hash("Worker123"), "worker", datetime.datetime.now().isoformat()),
        )


def _sqlite_migrate_columns(cur) -> None:
    user_columns = get_table_columns(cur, "users")
    if "phone" not in user_columns:
        cur.execute("ALTER TABLE users ADD COLUMN phone TEXT")
    if "profile_image" not in user_columns:
        cur.execute("ALTER TABLE users ADD COLUMN profile_image TEXT")

    post_columns = get_table_columns(cur, "posts")
    if "image_file" not in post_columns:
        cur.execute("ALTER TABLE posts ADD COLUMN image_file TEXT")

    history_columns = get_table_columns(cur, "history")
    if "image_file" not in history_columns:
        cur.execute("ALTER TABLE history ADD COLUMN image_file TEXT")

    message_columns = get_table_columns(cur, "messages")
    if "deleted_for_sender" not in message_columns:
        cur.execute("ALTER TABLE messages ADD COLUMN deleted_for_sender INTEGER NOT NULL DEFAULT 0")
    if "deleted_for_receiver" not in message_columns:
        cur.execute("ALTER TABLE messages ADD COLUMN deleted_for_receiver INTEGER NOT NULL DEFAULT 0")
    if "deleted_for_all" not in message_columns:
        cur.execute("ALTER TABLE messages ADD COLUMN deleted_for_all INTEGER NOT NULL DEFAULT 0")
    if "deleted_at" not in message_columns:
        cur.execute("ALTER TABLE messages ADD COLUMN deleted_at TEXT")

    settings_columns = get_table_columns(cur, "site_settings")
    if "disease_info" not in settings_columns:
        cur.execute("ALTER TABLE site_settings ADD COLUMN disease_info TEXT NOT NULL DEFAULT ''")
    if "indoor_info" not in settings_columns:
        cur.execute("ALTER TABLE site_settings ADD COLUMN indoor_info TEXT NOT NULL DEFAULT ''")
    if "iot_esp_ip" not in settings_columns:
        cur.execute("ALTER TABLE site_settings ADD COLUMN iot_esp_ip TEXT NOT NULL DEFAULT ''")

    iot_columns = get_table_columns(cur, "iot_readings")
    if "user_id" not in iot_columns:
        cur.execute("ALTER TABLE iot_readings ADD COLUMN user_id INTEGER")

    booking_columns = get_table_columns(cur, "analysis_bookings")
    if "confirmed_by" not in booking_columns:
        cur.execute("ALTER TABLE analysis_bookings ADD COLUMN confirmed_by INTEGER")
    if "confirmed_at" not in booking_columns:
        cur.execute("ALTER TABLE analysis_bookings ADD COLUMN confirmed_at TEXT")
    if "started_at" not in booking_columns:
        cur.execute("ALTER TABLE analysis_bookings ADD COLUMN started_at TEXT")


def _migrate_user_roles_sqlite(cur) -> None:
    try:
        cur.execute(
            "INSERT INTO users (username, password_hash, role, created_at) VALUES ('__role_probe__', 'x', 'worker', 'x')"
        )
        cur.execute("DELETE FROM users WHERE username = '__role_probe__'")
        return
    except sqlite3.IntegrityError:
        pass

    cur.execute(
        """
        CREATE TABLE users_role_migrated (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            phone TEXT UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin', 'user', 'worker')),
            created_at TEXT NOT NULL
        )
        """
    )
    cur.execute(
        """
        INSERT INTO users_role_migrated (id, username, phone, password_hash, role, created_at)
        SELECT id, username, phone, password_hash, role, created_at FROM users
        """
    )
    cur.execute("DROP TABLE users")
    cur.execute("ALTER TABLE users_role_migrated RENAME TO users")


def init_db() -> None:
    conn = get_db_connection()
    cur = conn

    if is_mssql():
        ensure_mssql_database()
        _run_mssql_schema(cur)
        existing_settings = cur.execute("SELECT id FROM site_settings WHERE id = 1").fetchone()
        if not existing_settings:
            cur.execute(
                "INSERT INTO site_settings (id, instagram_url, whatsapp_phone, updated_at) VALUES (1, '', '', ?)",
                (datetime.datetime.now().isoformat(),),
            )
        _seed_default_users(cur)
        conn.commit()
        conn.close()
        return

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            phone TEXT UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin', 'user')),
            created_at TEXT NOT NULL
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            details TEXT,
            image_file TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            image_file TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL,
            receiver_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            deleted_for_sender INTEGER NOT NULL DEFAULT 0,
            deleted_for_receiver INTEGER NOT NULL DEFAULT 0,
            deleted_for_all INTEGER NOT NULL DEFAULT 0,
            deleted_at TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(sender_id) REFERENCES users(id),
            FOREIGN KEY(receiver_id) REFERENCES users(id)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS friendships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user1_id INTEGER NOT NULL,
            user2_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            CHECK(user1_id < user2_id),
            UNIQUE(user1_id, user2_id),
            FOREIGN KEY(user1_id) REFERENCES users(id),
            FOREIGN KEY(user2_id) REFERENCES users(id)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS friend_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL,
            receiver_id INTEGER NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('pending', 'accepted', 'rejected')),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(sender_id, receiver_id),
            FOREIGN KEY(sender_id) REFERENCES users(id),
            FOREIGN KEY(receiver_id) REFERENCES users(id)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS post_likes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(post_id, user_id),
            FOREIGN KEY(post_id) REFERENCES posts(id),
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS post_replies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(post_id) REFERENCES posts(id),
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS post_reactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            reaction_type TEXT NOT NULL CHECK(reaction_type IN ('like', 'haha', 'angry', 'wow')),
            created_at TEXT NOT NULL,
            UNIQUE(post_id, user_id),
            FOREIGN KEY(post_id) REFERENCES posts(id),
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS site_settings (
            id INTEGER PRIMARY KEY CHECK(id = 1),
            instagram_url TEXT NOT NULL DEFAULT '',
            whatsapp_phone TEXT NOT NULL DEFAULT '',
            disease_info TEXT NOT NULL DEFAULT '',
            indoor_info TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL
        )
        """
    )

    _sqlite_migrate_columns(cur)

    existing_settings = cur.execute("SELECT id FROM site_settings WHERE id = 1").fetchone()
    if not existing_settings:
        cur.execute(
            "INSERT INTO site_settings (id, instagram_url, whatsapp_phone, updated_at) VALUES (1, '', '', ?)",
            (datetime.datetime.now().isoformat(),),
        )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS iot_readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            nitrogen REAL NOT NULL,
            phosphorus REAL NOT NULL,
            potassium REAL NOT NULL,
            temperature REAL NOT NULL,
            humidity REAL NOT NULL,
            rainfall REAL NOT NULL,
            ph REAL NOT NULL,
            soil_moisture REAL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS analysis_bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            duration_days INTEGER NOT NULL CHECK(duration_days IN (7, 14, 30)),
            status TEXT NOT NULL DEFAULT 'scheduled',
            confirmed_by INTEGER,
            confirmed_at TEXT,
            started_at TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(confirmed_by) REFERENCES users(id)
        )
        """
    )

    _sqlite_migrate_columns(cur)
    _seed_default_users(cur)
    _migrate_user_roles_sqlite(cur)
    conn.commit()
    conn.close()
