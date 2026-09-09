import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date, timedelta


def normalize(value):
    return re.sub(r"\s+", " ", (value or "").strip()).casefold()


def build_grouping_key(company, shipping_date, snapshot):
    stable = {
        "company": normalize(company),
        "date": str(shipping_date),
        "name": normalize(snapshot["name"]),
        "name2": normalize(snapshot.get("name2")),
        "country": normalize(snapshot["country_code"]),
        "postal_code": normalize(snapshot["postal_code"]),
        "city": normalize(snapshot["city"]),
        "street": normalize(snapshot["street"]),
        "street_number": normalize(snapshot["street_number"]),
    }
    raw = json.dumps(stable, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def common_package_count(counts):
    values = [int(value or 0) for value in counts]
    return max(values or [1])


@dataclass(frozen=True)
class OrderAvailability:
    """ERP independent input for the dispatch decision engine."""

    order: str
    customer_group: str
    address_key: str
    order_date: date
    open_qty: float
    available_qty: float
    available_net: float

    @property
    def fully_available(self):
        return self.open_qty > 0 and self.available_qty >= self.open_qty


@dataclass(frozen=True)
class DispatchDecision:
    order: str
    release: bool
    reason: str
    age_workdays: int


def workdays_between(start, end, holidays=()):
    """Completed Mon-Fri workdays after start; holidays are excluded."""
    start, end = _as_date(start), _as_date(end)
    holidays = {_as_date(value) for value in holidays}
    cursor, count = start + timedelta(days=1), 0
    while cursor <= end:
        if cursor.weekday() < 5 and cursor not in holidays:
            count += 1
        cursor += timedelta(days=1)
    return count


def decide_dispatch(orders, run_date, minimum_net=150.0, kindergarten_wait=5, holidays=()):
    """Apply the agreed customer-group, waiting and address-pooling rules."""
    ages = {
        row.order: workdays_between(row.order_date, run_date, holidays)
        for row in orders
    }
    threshold_candidates = [
        row
        for row in orders
        if row.customer_group != "Endkunde"
        and row.available_qty > 0
        and (
            row.customer_group != "Kindergarten"
            or row.fully_available
            or ages[row.order] >= kindergarten_wait
        )
    ]
    address_values = {}
    for row in threshold_candidates:
        address_values[row.address_key] = address_values.get(row.address_key, 0.0) + row.available_net

    result = []
    for row in orders:
        age = ages[row.order]
        if row.available_qty <= 0:
            result.append(DispatchDecision(row.order, False, "Kein Bestand verfügbar", age))
        elif row.customer_group == "Endkunde" and not row.fully_available:
            result.append(DispatchDecision(row.order, False, "Endkunde wartet auf Gesamtlieferung", age))
        elif row.fully_available:
            result.append(DispatchDecision(row.order, True, "Auftrag vollständig lieferbar", age))
        elif row.customer_group == "Kindergarten" and age < kindergarten_wait:
            remaining = kindergarten_wait - age
            result.append(DispatchDecision(row.order, False, f"Kindergarten-Wartefrist: noch {remaining} Werktag(e)", age))
        elif address_values.get(row.address_key, 0.0) >= float(minimum_net):
            result.append(DispatchDecision(row.order, True, "Mindestwarenwert je Lieferadresse erreicht", age))
        else:
            value = address_values.get(row.address_key, 0.0)
            result.append(DispatchDecision(row.order, False, f"Mindestwarenwert nicht erreicht ({value:.2f} EUR)", age))
    return result


def _as_date(value):
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))
