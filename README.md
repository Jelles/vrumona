## Start SQL Server

Run this command from the repository root to start a SQL Server 2022 container. It accepts the license agreement, exposes SQL Server on port 1433, and mounts the local `data` folder at `/backup` in the container.

```powershell
docker run -e ACCEPT_EULA=Y -e "MSSQL_SA_PASSWORD=Vrumona!Passw0rd" -p 1433:1433 -v "${PWD}/data:/backup" -d --name mssql mcr.microsoft.com/mssql/server:2022-latest
```

Connect to the server at `localhost,1433` using the `sa` account and the password specified in the command.

The password must be at least 8 characters and contain three of: uppercase, lowercase, digits, symbols. Otherwise SQL Server stops during setup. If you change it, also change it in `config.py`.

## Import a .bak file

Put the `.bak` file in the `data` folder and run:

```powershell
uv run restore_backup.py data/Tankbezetting.bak
```

This (re)creates the database `Tankbezetting`. An existing database with that name is overwritten.

## Make the data for Tableau

```powershell
uv run prepare_tableau_data.py
```

This reads the batches and CIPs, derives the status of every unit at every moment and writes to `output/`:

| File | Contents |
|---|---|
| `Capaciteit_Details.hyper` | one row per unit per time slice: status (Batch, CIP, Dirty, Clean - Available/Unavailable), batch info, bruto/netto |
| `Capaciteit_Overall.hyper` | one row per time slice for the whole syrup hall: number of tanks/mixers per status, bruto/netto capacity |
| `Vrumona POC - <year>.twbx` | a copy of the dashboard with these two extracts inside |

After opening the new `.twbx`, set the "Selecteer Periode" date filter to the new year (it is saved as 2018).

### Rules used

- Sources: `Tank_bezetting_en_CIP_zonder_rust` for the syrup tanks (PD017) and batch mixers (PD018), and `Tank_bezetting_en_CIP_met_rust_Loop` for the CIP installations (PD036). You can change both in `config.py`.
- Purge and Push Back are short flushes, not batches, so they are ignored. Events longer than 48 hours are registration errors and are dropped.
- After a CIP a unit is **Clean**. After a batch it is **Dirty** until the next CIP.
- A production week runs from the start of the shift (07-15, 15-23, 23-07) of the first mixer batch to the end of the shift of the last mixer batch. Batches on Sunday count toward the new week.
- **Bruto**: at least 1 batch mixer and at least 1 syrup tank are clean during a production week. **Netto**: bruto for at least 2 hours in a row. A unit counts as "Clean - Available" if it stays clean for 2 hours or more.
