# Why the new dashboards differ from the 2018 versions

We rebuilt the data for both dashboards directly from the database, following the rules in "Data opschonen". For 2018 the new results are close to the old dashboard, but not identical:

| 2018 | Old dashboard | New dashboard |
|---|---|---|
| Bruto availability | 68.0% | 70.1% |
| Netto availability | 55.0% | 61.6% |
| Unusable time | 13.0% | 8.5% |

The batches and CIPs themselves are the same: every tank batch in the old data is also in the new data, with exactly the same start and end times. The production weeks are also the same as before (see below). The differences come from three choices in how the data is processed.

## Production week: the same as before

A production week runs from the shift in which the first batch or CIP of the week starts to the shift in which the last one ends (shifts 07-15, 15-23, 23-07). This counts every syrup tank and batch mixer. After the last mixer batch, the tanks keep supplying the filling lines and are then cleaned, so the week usually ends on Saturday morning.

This matches the old weeks closely: 6,639 production hours in the new data against 6,634 in the old. Production in the weekend itself is rare: in 2018 only 17 mixer batches started on a Saturday.

## 1. Netto: the combination must last 2 hours

There is netto capacity when a clean batch mixer and a clean syrup tank are available together for at least 2 hours in a row.

- **New:** at least one mixer and at least one tank are clean at the same time, without interruption, for 2 hours or more.
- **Old:** each mixer and each tank was checked separately for 2 hours. So a short overlap of a few minutes could count as netto, while 2 hours made up of different mixers did not.

If we apply the old rule to the new data, netto drops to 59.8% and unusable time rises to 10.4%.

## 2. Short flushes are not batches

Purge and Push Back are short flushes of a mixer, usually a few minutes. A Purge happens right at the end of a cleaning run (CIP).

The old data counted 73 of these flushes as batches. As a result, a mixer that had just been cleaned looked busy, and after that "dirty" until its next cleaning run. Together that is about 500 hours in which the old dashboard showed a mixer as unavailable while it was actually clean. The new data does not count flushes as batches. This explains most of the difference in bruto.

## 3. Long tank batches are kept

A tank batch lasts from filling the tank until the filling line has emptied it. The old data left out every tank batch longer than 16.7 hours (1,000 minutes): 538 batches in 2018, about 1 in 5 tank batches. During those 10,559 hours the old dashboard showed the tank as clean and available, while it was actually full of syrup.

The new data keeps these batches, because they look like real batches: they have an amount and a filling line. As a result the tank overviews show more "Batch" time. The KPIs barely change, because there is almost always another clean tank.

## White days in the calendar

Some days in the calendar ("Capaciteit per dag") are white. On those days there was no production at all. Such a day is not part of a production week, so there is nothing to measure. **White means "no production", not "0% capacity".**

Both versions have about 20 white days, mostly Saturdays. The most visible difference is 1 January. In the old dashboard it was coloured, because its first production week started on 1 January at 07:00. But clicking it showed no data, because nothing happened that day. In the new data, production starts on 2 January, so 1 January is white.

## Workshop dashboard ("workshop hour v2")

This dashboard uses the same new data and status rules, in its own layout. Its own definitions are kept:

- "Beschikbaar" means no batch or CIP is running.
- Bruto means a clean mixer and a clean tank at any moment, without production weeks or the 2-hour rule.

The old workshop data left out even more than the old capacity dashboard:

- **Every tank batch longer than about 12 hours.** That's why the new version shows much more tank batch time (33,701 hours against 11,181 before). In the week timeline, the tanks show light green (Batch) where the old version showed dark blue (Clean).
- **Every CIP longer than 2 hours:** 78 cleaning runs in 2018. Without the CIP, the old version showed the unit as "Dirty" until its next batch, while it was actually being cleaned and was clean after that. For example, mixer Unit 200 on 1 May 2018 was "Dirty" from 14:48 to 23:15 in the old version. In reality a CIP ran from 14:48 to 18:57, and the mixer was clean after that.

Bruto over the whole year is 77.3% now, against 74.1% before.

