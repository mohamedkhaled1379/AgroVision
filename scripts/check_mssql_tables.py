import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

from database import ensure_mssql_database, get_db_connection, init_db, is_mssql, table_exists

if not is_mssql():
    raise SystemExit("DB_BACKEND is not mssql. Check d:\\agro\\.env")

ensure_mssql_database()
conn = get_db_connection()
rows = conn.execute(
    "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE' ORDER BY TABLE_NAME"
).fetchall()
print("Tables:", [r["TABLE_NAME"] for r in rows] if rows else "NONE")
conn.close()

if not rows or not table_exists(get_db_connection(), "users"):
    print("Creating tables...")
    init_db()
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE' ORDER BY TABLE_NAME"
    ).fetchall()
    print("Tables after init:", [r["TABLE_NAME"] for r in rows])
    conn.close()
