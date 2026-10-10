"""Restore a .bak file into the SQL Server container.

Usage:
    uv run restore_backup.py data/Tankbezetting.bak

The .bak file must be in the data/ folder, because that folder is mounted in the
container as /backup. An existing database with the same name is overwritten.
"""

import sys
from pathlib import Path

import pymssql

import config

bak_file = Path(sys.argv[1]) if len(sys.argv) > 1 else config.DATA_DIR / "Tankbezetting.bak"
backup_path = f"/backup/{bak_file.name}"  # path inside the container

conn = pymssql.connect(server=config.SERVER, port=config.PORT, user=config.USER, password=config.PASSWORD, database="master", autocommit=True)
cursor = conn.cursor(as_dict=True)

cursor.execute(f"RESTORE FILELISTONLY FROM DISK = '{backup_path}'")

files = cursor.fetchall()

moves = ", ".join(
    f"MOVE '{f['LogicalName']}' TO '/var/opt/mssql/data/{f['LogicalName']}"
    f"{'.ldf' if f['Type'] == 'L' else '.mdf'}'"
    for f in files
)

print(f"Restoring {backup_path} as database {config.DATABASE} ...")

cursor.execute(f"IF DB_ID('{config.DATABASE}') IS NOT NULL ALTER DATABASE [{config.DATABASE}] SET SINGLE_USER WITH ROLLBACK IMMEDIATE")
cursor.execute(f"RESTORE DATABASE [{config.DATABASE}] FROM DISK = '{backup_path}' WITH {moves}, REPLACE, RECOVERY")

while cursor.nextset():  # wait until SQL Server has finished the restore
    pass

cursor.execute(f"USE [{config.DATABASE}]; SELECT TABLE_SCHEMA + '.' + TABLE_NAME AS name FROM INFORMATION_SCHEMA.TABLES")

print("Done. Tables:", ", ".join(row["name"] for row in cursor.fetchall()))

conn.close()
