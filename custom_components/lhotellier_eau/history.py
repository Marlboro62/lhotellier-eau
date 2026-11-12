"""Construction des points d'historique (relevés et factures), sans dépendance à Home Assistant."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta, tzinfo

from .api import Bill, MeterRead


@dataclass(frozen=True)
class HistoryPoint:
    start: datetime  # en UTC, à l'heure pile
    state: float | None
    sum: float


def _hour(when: datetime) -> datetime:
    return when.astimezone(UTC).replace(minute=0, second=0, microsecond=0)


def _cumulate(rows: list[tuple[datetime, float | None, float]]) -> list[HistoryPoint]:
    """rows : (début, état, valeur de la période), triés par date croissante.

    Un point à zéro est ajouté une heure avant le premier, pour que la valeur
    du premier relevé (ou de la première facture) soit comptée à sa date.
    """
    if not rows:
        return []
    by_hour: dict[datetime, tuple[float | None, float]] = {}
    for start, state, delta in rows:
        old = by_hour.get(start)
        by_hour[start] = (state, delta + (old[1] if old else 0.0))
    starts = sorted(by_hour)
    points = [HistoryPoint(start=starts[0] - timedelta(hours=1), state=None, sum=0.0)]
    total = 0.0
    for start in starts:
        state, delta = by_hour[start]
        total = round(total + delta, 3)
        points.append(HistoryPoint(start=start, state=state, sum=total))
    return points


def consumption_points(reads: list[MeterRead]) -> list[HistoryPoint]:
    """Consommation cumulée (m³), datée à chaque relevé."""
    rows: list[tuple[datetime, float | None, float]] = []
    previous: MeterRead | None = None
    for read in sorted(reads, key=lambda r: r.date):
        delta = read.consumption
        if delta is None and previous and read.index is not None and previous.index is not None:
            delta = read.index - previous.index
        if delta is not None and delta >= 0:
            rows.append((_hour(read.date), read.index, delta))
        previous = read
    points = _cumulate(rows)
    if points and rows and rows[0][1] is not None:
        # index avant le premier relevé connu
        points[0] = HistoryPoint(points[0].start, rows[0][1] - rows[0][2], 0.0)
    return points


def cost_points(bills: list[Bill], tz: tzinfo) -> list[HistoryPoint]:
    """Montants facturés cumulés (€), datés à chaque facture (minuit, heure locale)."""
    rows: list[tuple[datetime, float | None, float]] = [
        (_hour(datetime.combine(bill.date, time(0, 0), tzinfo=tz)), bill.amount, bill.amount)
        for bill in sorted(bills, key=lambda b: b.date)
        if bill.amount is not None
    ]
    return _cumulate(rows)
