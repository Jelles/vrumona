"""Settings shared by restore_backup.py and prepare_tableau_data.py."""

from pathlib import Path

# SQL Server in Docker (see README.md)
SERVER = "localhost"
PORT = 1433
USER = "sa"
PASSWORD = "Vrumona!Passw0rd"
DATABASE = "Tankbezetting"

# Tables in the database
# - EVENTS_TABLE: batches and CIPs of the syrup tanks (PD017) and batch mixers (PD018)
# - PD036_TABLE:  the only table that also contains the CIP installations (PD036)
EVENTS_TABLE = "dbo.Tank_bezetting_en_CIP_zonder_rust"
PD036_TABLE = "dbo.Tank_bezetting_en_CIP_met_rust_Loop"

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"  # mounted in the container as /backup
OUTPUT_DIR = ROOT / "output"
TEMPLATE_TWBX = DATA_DIR / "Vrumona POC - final.twbx"
