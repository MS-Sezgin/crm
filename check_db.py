"""Database connection check. Run: python check_db.py

Shows which database the app would use, whether the connection works, and how many
rows each table has. Use it first when the app cannot start.
"""
from database import ConfigError, CrmRepositories, Database, DatabaseError, DbConfig

try:
    config = DbConfig.load()
except ConfigError as error:
    raise SystemExit(f"SETTINGS PROBLEM: {error}")

print(f"Host: {config.host}:{config.port}   Database: {config.dbname}   User: {config.user}")
try:
    with Database(config) as db:
        print("Connection: OK")
        if not db.table_exists("Kursiyerler"):
            raise SystemExit("The tables do not exist yet. Run: python migrate_excel_to_db.py --create-schema")
        for table, count in CrmRepositories(db).counts().items():
            print(f"  {table:15} {count:>5} row(s)")
except DatabaseError as error:
    raise SystemExit(f"CONNECTION FAILED: {error}")
