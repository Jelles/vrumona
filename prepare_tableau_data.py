"""Prepare the batch mixer and syrup tank data for the Tableau dashboard.

Reads the batches and CIPs from SQL Server, works out the status of every unit at
every moment (Batch, CIP, Dirty or Clean) and when there was capacity available,
and writes the data for two Tableau dashboards to the output folder:

    Capacity dashboard ("Vrumona POC - final")
        Capaciteit_Details.hyper       one row per unit per time slice
        Capaciteit_Overall.hyper       one row per time slice for the whole syrup hall
        Vrumona POC - <year>.twbx      the dashboard with this data inside

    Workshop dashboard ("Vrumona workshop hour v2"), same data in an older layout
        AvailabilityPerUnit.hyper
        AvailabilityOverall.hyper
        Vrumona workshop hour v2 - <year>.twbx

Every table is also written as a .csv file with the same name, for Excel, SQL or a
new Tableau connection.

Run it with:  uv run prepare_tableau_data.py
The "# %%" lines split the script into cells, so you can also run it step by step
in VS Code (click "Run Cell") and look at the tables in between.
"""

import zipfile

import numpy as np
import pandas as pd
import pantab
import pymssql

import config

TANKS, MIXERS, CIP_UNITS = "PD017", "PD018", "PD036"  # process parts (procesdelen)

MIN_AVAILABLE = pd.Timedelta(hours=2)  # netto: available for at least 2 hours in a row
MAX_EVENT = pd.Timedelta(hours=48)  # events that take longer are registration errors
SHIFT_START = pd.Timedelta(hours=7)  # shifts are 07-15, 15-23 and 23-07
NOT_A_BATCH = ["Purge", "Push Back"]  # short flushes of the mixer, not production


# %% 1. Read the batches and CIPs from the database

def read_sql(sql):
    with pymssql.connect(server=config.SERVER, port=config.PORT, user=config.USER, password=config.PASSWORD, database=config.DATABASE) as conn:
        cursor = conn.cursor(as_dict=True)
        cursor.execute(sql)

        return pd.DataFrame(cursor.fetchall())


raw = read_sql(f"""
    SELECT UNIT_NAME, PD, RECIPE_NAME, PROD_NAME, BATCH_ID, START_BATCH, END_BATCH
    FROM {config.EVENTS_TABLE}
    WHERE PD IN ('{TANKS}', '{MIXERS}')
""")

raw["Soort"] = np.select(
    [raw.RECIPE_NAME.eq("Batch") & ~raw.PROD_NAME.isin(NOT_A_BATCH),
     raw.RECIPE_NAME.str.contains("CIP", na=False)],
    ["Batch", "CIP"],
    default="",
)

if config.PD036_TABLE:
    raw_pd036 = read_sql(f"""
        SELECT UNIT_NAME, PD, RECIPE_NAME, BATCH_ID, START_BATCH, END_BATCH
        FROM {config.PD036_TABLE}
        WHERE PD = '{CIP_UNITS}'
    """)

    raw_pd036["Soort"] = "CIP"
    raw = pd.concat([raw, raw_pd036])

print(f"Read {len(raw):,} rows from the database")


# %% 2. Clean up: keep only real batches and CIPs with a sensible duration

raw = raw[raw.Soort != ""]

events = pd.DataFrame({
    "Unit": raw.UNIT_NAME,
    "Procesdeel": raw.PD.str.strip(),
    "Soort": raw.Soort,
    "Batch_ID": raw.BATCH_ID.astype("float64"),
    "Start": raw.START_BATCH,
    "Eind": raw.END_BATCH,
})

duration = events.Eind - events.Start
events = events[(duration > pd.Timedelta(0)) & (duration <= MAX_EVENT)]

# The period is set by the tank and mixer data. PD036 data outside it is cut off.
main = events[events.Procesdeel != CIP_UNITS]
period_start = main.Start.min().floor("D")
period_end = main.Eind.max().ceil("D")
year = main.Start.dt.year.mode()[0]  # the year most of the data is from
events["Start"] = events.Start.clip(period_start, period_end)
events["Eind"] = events.Eind.clip(period_start, period_end)
events = events[events.Start < events.Eind].reset_index(drop=True)

print(f"{len(events):,} batches and CIPs from {period_start:%d-%m-%Y} to {period_end:%d-%m-%Y}")


# %% 3. Production weeks
# A production week starts at the start of the shift in which the first batch or CIP of
# that week started (on any tank or mixer), and ends at the end of the shift in which
# the last one ended. The tanks count too: after the last mixer batch they keep
# supplying the filling lines, and then they are cleaned.

def shift_start(times):
    return (times - SHIFT_START).dt.floor("8h") + SHIFT_START


def shift_end(times):
    return (times - SHIFT_START).dt.ceil("8h") + SHIFT_START


def monday_of(times):
    days = times.dt.normalize()
    return days - pd.to_timedelta(days.dt.weekday, unit="D")


week_events = events[events.Procesdeel.isin([TANKS, MIXERS])]
# Production starts up on Sunday evening, so an event on Sunday belongs to the new week
weeks = (week_events.groupby(monday_of(week_events.Start + pd.Timedelta(days=1))).agg(Start=("Start", "min"), Eind=("Eind", "max")))
weeks["Start"] = shift_start(weeks.Start)
weeks["Eind"] = shift_end(weeks.Eind)

# Week 1 is the week with 1 January in it. The last days of December can be week 53.
first_monday = monday_of(pd.Series(pd.Timestamp(year, 1, 1)))[0]
week_number = (weeks.index - first_monday).days // 7 + 1
weeks["Productieweek"] = [f"Week {n}" for n in week_number]

print(f"{len(weeks)} production weeks")


# %% 4. Cut the period into time slices
# Every start or end of an event, every full hour and every week boundary is a cut
# point. Inside a slice nothing changes, so each unit has exactly one status per slice
# and all units share the same slices. The full hours make it possible to show the
# capacity per hour and per day in the dashboard.

cut_points = (pd.concat([pd.Series(pd.date_range(period_start, period_end, freq="h")), events.Start, events.Eind, weeks.Start, weeks.Eind]).drop_duplicates().sort_values())
cut_points = cut_points[cut_points.between(period_start, period_end)].to_numpy()

slices = pd.DataFrame({"Starttijd": cut_points[:-1], "Eindtijd": cut_points[1:]})
slices["Seconden"] = (slices.Eindtijd - slices.Starttijd).dt.total_seconds().astype("int64")
slices["Productieweek"] = None  # outside a production week

for w in weeks.itertuples():
    in_week = (slices.Starttijd >= w.Start) & (slices.Starttijd < w.Eind)
    slices.loc[in_week, "Productieweek"] = w.Productieweek

print(f"{len(slices):,} time slices")


# %% 5. Status of every unit in every time slice
#   Batch / CIP        an event is running (both at once: "CIP & Batch")
#   Clean              the last finished event was a CIP
#   Dirty              the last finished event was a batch
#   Niet in gebruik    before the first batch or CIP of the unit (status unknown)
#   PD036 units are "CIP_Batch" while running and "Beschikbaar" otherwise.

slice_starts = pd.DatetimeIndex(slices.Starttijd)

def unit_status(unit_events, procesdeel):
    n = len(slices)
    in_batch = np.zeros(n, dtype=bool)
    in_cip = np.zeros(n, dtype=bool)
    batch_nr = np.full(n, -1)  # row in `events` of the batch that is running
    last_finished = pd.Series(None, index=range(n), dtype=object)

    for event in unit_events.sort_values("Eind").itertuples():
        first = slice_starts.searchsorted(event.Start)  # first slice of the event
        after = slice_starts.searchsorted(event.Eind)  # first slice after the event
        
        if event.Soort == "Batch":
            in_batch[first:after] = True
            batch_nr[first:after] = event.Index
        else:
            in_cip[first:after] = True
        if after < n:
            last_finished[after] = event.Soort
    
    last_finished = last_finished.ffill()  # until the next event finishes

    if procesdeel == CIP_UNITS:
        status = np.where(in_cip, "CIP_Batch", "Beschikbaar")
    else:
        status = np.select(
            [in_batch & in_cip, in_batch, in_cip, last_finished == "CIP", last_finished == "Batch"],
            ["CIP & Batch", "Batch", "CIP", "Clean", "Dirty"],
            default="Niet in gebruik",
        )
    return status, batch_nr


parts = []

for (unit, procesdeel), unit_events in events.groupby(["Unit", "Procesdeel"]):
    part = slices.copy()
    part["slice_nr"] = slices.index
    part["Unit"] = unit
    part["Procesdeel"] = procesdeel
    part["Status"], part["batch_nr"] = unit_status(unit_events, procesdeel)
    parts.append(part)

details = pd.concat(parts, ignore_index=True)

# Add the batch details to the slices in which a batch is running
batches = events[["Batch_ID", "Start", "Eind"]].rename(columns={"Start": "Batch_StartTime", "Eind": "Batch_FinishTime"})
details = details.merge(batches, left_on="batch_nr", right_index=True, how="left")
details["Batch_Duur"] = (details.Batch_FinishTime - details.Batch_StartTime).dt.total_seconds().astype("Int64")

print(f"{details.Unit.nunique()} units, {len(details):,} rows")


# %% 6. Availability per unit
#   Capaciteit_Bruto: the unit is clean, during a production week
#   Capaciteit_Netto: ...and stays like that for at least 2 hours in a row
#   A clean unit becomes "Clean - Available" (netto) or "Clean - Unavailable".

def lasts_two_hours(available, seconds, unit=None):
    """True where `available` holds for an uninterrupted stretch of at least 2 hours."""
    new_stretch = available.ne(available.shift())
    
    if unit is not None:
        new_stretch |= unit.ne(unit.shift())

    stretch_seconds = seconds.groupby(new_stretch.cumsum()).transform("sum")
    
    return available & (stretch_seconds >= MIN_AVAILABLE.total_seconds())


in_week = details.Productieweek.notna()
details["Capaciteit_Bruto"] = details.Status.isin(["Clean", "Beschikbaar"]) & in_week
details["Capaciteit_Netto"] = lasts_two_hours(details.Capaciteit_Bruto, details.Seconden, details.Unit)

clean = details.Status == "Clean"
details.loc[clean & details.Capaciteit_Netto, "Status"] = "Clean - Available"
details.loc[clean & ~details.Capaciteit_Netto, "Status"] = "Clean - Unavailable"

# As in the original data: no netto value for PD036, so it does not count in the KPIs
details["Capaciteit_Netto"] = details.Capaciteit_Netto.astype("boolean")
details.loc[details.Procesdeel == CIP_UNITS, "Capaciteit_Netto"] = pd.NA


# %% 7. Overall: the whole syrup hall per time slice
#   Bruto: at least 1 batch mixer AND at least 1 syrup tank available
#   Netto: bruto for at least 2 hours in a row

def count(procesdeel, condition):
    """Number of units of a process part for which `condition` holds, per time slice."""
    rows = details.Procesdeel == procesdeel
    
    return condition[rows].groupby(details.slice_nr[rows]).sum().to_numpy()


status = details.Status
overall = slices.copy()
overall["Aantal_Mengtanks_Beschikbaar"] = count(TANKS, details.Capaciteit_Bruto)
overall["Aantal_Batchmixers_Beschikbaar"] = count(MIXERS, details.Capaciteit_Bruto)
overall["Aantal_Mengtanks_Clean"] = count(TANKS, status.str.startswith("Clean"))
overall["Aantal_Mengtanks_Batch"] = count(TANKS, status.isin(["Batch", "CIP & Batch"]))
overall["Aantal_Mengtanks_CIP"] = count(TANKS, status.isin(["CIP", "CIP & Batch"]))
overall["Aantal_Batchmixers_Clean"] = count(MIXERS, status.str.startswith("Clean"))
overall["Aantal_Batchmixers_Batch"] = count(MIXERS, status.isin(["Batch", "CIP & Batch"]))
overall["Aantal_BatchMixers_CIP"] = count(MIXERS, status.isin(["CIP", "CIP & Batch"]))
overall["Capaciteit_Batchmixers"] = overall.Aantal_Batchmixers_Beschikbaar > 0
overall["Capaciteit_Mengtanks"] = overall.Aantal_Mengtanks_Beschikbaar > 0
overall["Capaciteit_Bruto"] = overall.Capaciteit_Batchmixers & overall.Capaciteit_Mengtanks
overall["Capaciteit_Netto"] = lasts_two_hours(overall.Capaciteit_Bruto, overall.Seconden)

# Same KPIs as at the top of the dashboard (computed over the production weeks)
weeks_only = overall[overall.Productieweek.notna()]
total = weeks_only.Seconden.sum()
bruto = weeks_only.Seconden[weeks_only.Capaciteit_Bruto].sum() / total
netto = weeks_only.Seconden[weeks_only.Capaciteit_Netto].sum() / total
print(f"Bruto beschikbaarheid {bruto:.1%}, netto {netto:.1%}, onbenutbare tijd {bruto - netto:.1%}")


# %% 8. Capacity dashboard ("Vrumona POC - final")
# Write the two extracts with the same column names as the original ones, and a copy of
# the dashboard with the new extracts inside.

def write_files(table, name):
    """Write a table as .hyper (for the dashboards) and as .csv (for Excel, SQL or Tableau)."""
    hyper_file = config.OUTPUT_DIR / f"{name}.hyper"
    pantab.frame_to_hyper(table, hyper_file, table=("Extract", "Extract"))
    # Batch_ID is the only decimal column: write 340735 instead of 340735.0
    table.to_csv(config.OUTPUT_DIR / f"{name}.csv", index=False, float_format="%.0f")
    print(f"Written {name}.hyper and {name}.csv")
    
    return hyper_file


def make_twbx(template, twbx_file, new_extracts):
    """Copy a .twbx file (a zip file with the workbook and its extracts) with new extracts."""
    with (zipfile.ZipFile(template) as old,
          zipfile.ZipFile(twbx_file, "w", zipfile.ZIP_DEFLATED) as new):
        missing = set(new_extracts) - set(old.namelist())
        
        if missing:
            raise ValueError(f"{template.name} does not contain {missing}")
        for item in old.infolist():
            if item.filename in new_extracts:
                new.write(new_extracts[item.filename], item.filename)
            else:
                new.writestr(item, old.read(item.filename))
    print(f"Written {twbx_file.name}")


config.OUTPUT_DIR.mkdir(exist_ok=True)

# Both dashboards' colours and filters expect 10 characters, e.g. "PD017     "
details["Procesdeel"] = details.Procesdeel.str.ljust(10)

details_file = write_files(details[[
    "Seconden", "Starttijd", "Eindtijd", "Status", "Unit", "Procesdeel", "Productieweek",
    "Batch_ID", "Batch_StartTime", "Batch_FinishTime", "Capaciteit_Netto",
    "Capaciteit_Bruto", "Batch_Duur",
]], "Capaciteit_Details")
overall_file = write_files(overall[[
    "Productieweek", "Starttijd", "Eindtijd", "Seconden", "Capaciteit_Batchmixers",
    "Capaciteit_Mengtanks", "Capaciteit_Bruto", "Capaciteit_Netto",
    "Aantal_Mengtanks_Beschikbaar", "Aantal_Batchmixers_Beschikbaar",
    "Aantal_Mengtanks_Clean", "Aantal_Mengtanks_Batch", "Aantal_Mengtanks_CIP",
    "Aantal_Batchmixers_Clean", "Aantal_Batchmixers_Batch", "Aantal_BatchMixers_CIP",
]], "Capaciteit_Overall")

make_twbx(config.POC_TWBX, config.OUTPUT_DIR / f"Vrumona POC - {year}.twbx", {
    "Data/Extracts/Capaciteit_Details Extract.hyper": details_file,
    "Data/Extracts/Capaciteit_Overall Extract.hyper": overall_file,
})


# %% 9. Workshop dashboard ("Vrumona workshop hour v2")
# An earlier version of the dashboard. It uses the same statuses, but only for the tanks
# and mixers, has no production weeks or netto, and uses other column names:
#   Status            just "Clean" (no Available / Unavailable)
#   Beschikbaar       1 when no batch or CIP is running, otherwise 0
#   Bruto_Capaciteit  at least 1 clean mixer and at least 1 clean tank, at any moment
#   Minutes           number of whole minutes (hh:mm:00) inside the time slice

def whole_minutes(start, end):
    return (end.dt.ceil("min") - start.dt.ceil("min")) // pd.Timedelta(minutes=1)


units = details[details.Procesdeel.str.strip().isin([TANKS, MIXERS])].reset_index(drop=True)
status = units.Status.replace({"Clean - Available": "Clean", "Clean - Unavailable": "Clean"})

per_unit = pd.DataFrame({
    "aaID": units.index,
    "Minutes": whole_minutes(units.Starttijd, units.Eindtijd),
    "Seconds": units.Seconden,
    "aaValuePeriodStartTime": units.Starttijd,
    "aaValuePeriodEndTime": units.Eindtijd,
    "Beschikbaar": (~status.isin(["Batch", "CIP", "CIP & Batch"])).astype("int64"),
    "Status": status,
    "Unit": units.Unit,
    "Procesdeel": units.Procesdeel,
})

# One column per unit with its status, e.g. "PD17_Tank_101"
unit_columns = status.groupby([units.slice_nr, units.Unit]).first().unstack()
unit_columns.columns = unit_columns.columns.str.replace(":", "_").str.replace(" ", "_")
tank_columns = [c for c in unit_columns.columns if "Tank" in c]
mixer_columns = [c for c in unit_columns.columns if "Unit" in c]

overall_v2 = pd.DataFrame({
    "Minutes": whole_minutes(overall.Starttijd, overall.Eindtijd),
    "Seconds": overall.Seconden,
    "aaValuePeriodStartTime": overall.Starttijd,
    "aaValuePeriodEndTime": overall.Eindtijd,
    "Bruto_Capaciteit": (overall.Aantal_Batchmixers_Clean > 0) & (overall.Aantal_Mengtanks_Clean > 0),
})

overall_v2 = overall_v2.join(unit_columns[tank_columns + mixer_columns])
overall_v2["PD018_Capaciteit"] = overall.Aantal_Batchmixers_Clean > 0
overall_v2["PD17_Capaciteit"] = overall.Aantal_Mengtanks_Clean > 0
overall_v2["Tanks_Clean"] = overall.Aantal_Mengtanks_Clean
overall_v2["Tanks_Batch"] = overall.Aantal_Mengtanks_Batch
overall_v2["Tanks_CIP"] = overall.Aantal_Mengtanks_CIP
overall_v2["Mixers_Clean"] = overall.Aantal_Batchmixers_Clean
overall_v2["Mixers_Batch"] = overall.Aantal_Batchmixers_Batch
overall_v2["Mixers_CIP"] = overall.Aantal_BatchMixers_CIP

per_unit_file = write_files(per_unit, "AvailabilityPerUnit")
overall_v2_file = write_files(overall_v2, "AvailabilityOverall")

make_twbx(config.WORKSHOP_TWBX, config.OUTPUT_DIR / f"Vrumona workshop hour v2 - {year}.twbx", {
    "Data/v2/AvailabilityPerUnit.hyper": per_unit_file,
    "Data/v2/AvailabilityOverall.hyper": overall_v2_file,
})
