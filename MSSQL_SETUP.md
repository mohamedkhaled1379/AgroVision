# Microsoft SQL Server Setup (AgroVision AI)

AgroVision supports **SQLite** (default) and **Microsoft SQL Server** (SSMS).

## 1. Install SQL Server

1. Install [SQL Server Express](https://www.microsoft.com/en-us/sql-server/sql-server-downloads) or Developer edition.
2. Install [SQL Server Management Studio (SSMS)](https://learn.microsoft.com/en-us/sql/ssms/download-sql-server-management-studio-ssms).
3. Install **ODBC Driver 18 for SQL Server** (included with recent SSMS installs).

## 2. Enable SQL login (if using `sa`)

In SSMS:

1. Connect to your instance (e.g. `localhost\SQLEXPRESS`).
2. Server Properties → Security → **SQL Server and Windows Authentication mode**.
3. Restart SQL Server service.
4. Security → Logins → `sa` → set a strong password.

## 3. Configure AgroVision

```powershell
cd d:\agro
copy .env.example .env
```

Edit `.env`:

```env
DB_BACKEND=mssql
MSSQL_SERVER=localhost\SQLEXPRESS
MSSQL_DATABASE=AgroVision
MSSQL_USER=sa
MSSQL_PASSWORD=YourStrongPassword123!
MSSQL_DRIVER=ODBC Driver 18 for SQL Server
MSSQL_TRUST_SERVER_CERTIFICATE=yes
```

Install Python driver:

```powershell
.\.venv\Scripts\pip.exe install pyodbc
```

## 4. Create tables (automatic)

Start the app — it creates the `AgroVision` database and tables:

```powershell
.\run_agro.ps1
```

Or run schema manually in SSMS: open `sql\mssql_schema.sql` and execute.

## 5. Migrate existing SQLite data

If you already have `agro_users.db`:

```powershell
$env:DB_BACKEND="mssql"
$env:MSSQL_SERVER="localhost\SQLEXPRESS"
$env:MSSQL_DATABASE="AgroVision"
$env:MSSQL_USER="sa"
$env:MSSQL_PASSWORD="YourStrongPassword123!"
.\.venv\Scripts\python.exe scripts\migrate_sqlite_to_mssql.py --reset-target
```

`--reset-target` drops and recreates SQL Server tables, then copies all rows from SQLite.

## 6. Switch back to SQLite

In `.env`:

```env
DB_BACKEND=sqlite
DATABASE_PATH=agro_users.db
```

## Files

| File | Purpose |
|------|---------|
| `database.py` | Connection layer (SQLite + SQL Server) |
| `sql/mssql_schema.sql` | Create tables (SSMS or auto init) |
| `sql/mssql_reset.sql` | Drop all tables before re-import |
| `scripts/migrate_sqlite_to_mssql.py` | Copy data from SQLite |

## View data in SSMS

1. Connect to `localhost\SQLEXPRESS`.
2. Databases → **AgroVision**.
3. Tables → `dbo.users`, `dbo.iot_readings`, etc.

Default logins after init: `admin` / `admin123`, `worker` / `Worker123`.
