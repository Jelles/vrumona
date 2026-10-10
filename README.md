## Start SQL Server

Run this command from the repository root to start a SQL Server 2022 container. It accepts the license agreement, exposes SQL Server on port 1433, and mounts the local `data` folder at `/backup` in the container.

```powershell
docker run -e ACCEPT_EULA=Y -e "MSSQL_SA_PASSWORD=Vrumona!Passw0rd" -p 1433:1433 -v "${PWD}/data:/backup" -d --name mssql mcr.microsoft.com/mssql/server:2022-latest
```

Connect to the server at `localhost,1433` using the `sa` account and the password specified in the command.

If you change the password, also change it in `config.py`.

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

This reads the batches and CIPs, works out the status of every unit at every moment, and writes the data for two dashboards to `output/`:

| File | Contents |
|---|---|
| **Capacity dashboard** (`Vrumona POC - final`) | |
| `Capaciteit_Details.hyper` | one row per unit per time slice: status (Batch, CIP, Dirty, Clean - Available/Unavailable), batch info, bruto/netto |
| `Capaciteit_Overall.hyper` | one row per time slice for the whole syrup hall: number of tanks/mixers per status, bruto/netto capacity |
| `Vrumona POC - <year>.twbx` | a copy of the dashboard with these two extracts inside |
| **Workshop dashboard** (`Vrumona workshop hour v2`) | |
| `AvailabilityPerUnit.hyper` | the same statuses per unit in the older layout, with `Beschikbaar` = 1 when no batch or CIP is running |
| `AvailabilityOverall.hyper` | one row per time slice with a column per unit and bruto = a clean mixer and a clean tank at any moment |
| `Vrumona workshop hour v2 - <year>.twbx` | a copy of the workshop dashboard with these two extracts inside |

Each `.hyper` file is also written as a `.csv` file with the same name (comma-separated), for Excel, SQL or a new Tableau connection. `Capaciteit_Details.csv` has about 1.5 million rows, more than Excel can show; Tableau and SQL read it fine.

Open the `.twbx` files with Tableau Reader or Tableau Desktop. In the capacity dashboard, set the "Selecteer Periode" date filter to the new year (it is saved as 2018).

Why the 2018 numbers differ slightly from the original dashboards is explained in [differences_explained.md](differences_explained.md).