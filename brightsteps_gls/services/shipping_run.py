import hashlib
import json

import frappe
from frappe.utils import flt, getdate, nowdate

from brightsteps_gls.services.domain import OrderAvailability, decide_dispatch, normalize


def _address_key(company, address_name):
    address = frappe.get_doc("Address", address_name)
    parts = [company, address.address_title, address.address_line1, address.address_line2,
             address.pincode, address.city, address.country]
    return hashlib.sha256("|".join(normalize(value) for value in parts).encode()).hexdigest()


def _holidays(settings):
    if not settings.holiday_list:
        return []
    return frappe.get_all("Holiday", filters={"parent": settings.holiday_list}, pluck="holiday_date")


def _warehouse(item, order):
    return item.warehouse or frappe.db.get_value("Company", order.company, "default_warehouse")


def _free_stock(item_code, warehouse, cache):
    key = (item_code, warehouse)
    if key not in cache:
        if not warehouse:
            cache[key] = 0.0
        else:
            cache[key] = max(0.0, flt(frappe.db.get_value(
                "Bin", {"item_code": item_code, "warehouse": warehouse}, "actual_qty"
            )))
    return cache[key]


def analyse_open_orders(run_date=None):
    run_date = getdate(run_date or nowdate())
    settings = frappe.get_single("Shipping Run Settings")
    stock = {}
    rows, availability = [], []
    orders = frappe.get_all(
        "Sales Order",
        filters={"docstatus": 1, "status": ["not in", ["Closed", "Completed", "Cancelled"]]},
        fields=["name", "customer", "customer_group", "company", "transaction_date", "shipping_address_name", "customer_address"],
        order_by="transaction_date asc, creation asc",
    )
    for base in orders:
        address_name = base.shipping_address_name or base.customer_address
        if not address_name:
            continue
        doc = frappe.get_doc("Sales Order", base.name)
        allocations, open_qty, available_qty, available_net = [], 0.0, 0.0, 0.0
        for item in doc.items:
            outstanding = max(0.0, flt(item.qty) - flt(item.delivered_qty))
            if outstanding <= 0:
                continue
            is_stock = frappe.db.get_value("Item", item.item_code, "is_stock_item")
            warehouse = _warehouse(item, doc)
            available = outstanding if not is_stock else min(outstanding, _free_stock(item.item_code, warehouse, stock))
            if is_stock:
                stock[(item.item_code, warehouse)] -= available
            open_qty += outstanding
            available_qty += available
            available_net += available * flt(item.net_rate or item.rate)
            allocations.append({
                "item_code": item.item_code, "item_name": item.item_name,
                "sales_order_item": item.name, "warehouse": warehouse,
                "conversion_factor": flt(item.conversion_factor) or 1.0,
                "open_qty": outstanding, "qty": available,
                "net_rate": flt(item.net_rate or item.rate),
            })
        if not allocations:
            continue
        group = base.customer_group
        canonical = "Endkunde" if group == settings.end_customer_group else (
            "Kindergarten" if group == settings.kindergarten_group else group
        )
        key = _address_key(base.company, address_name)
        availability.append(OrderAvailability(
            base.name, canonical, key, getdate(base.transaction_date), open_qty, available_qty, available_net
        ))
        rows.append({
            "sales_order": base.name, "customer": base.customer, "customer_group": group,
            "shipping_address": address_name, "address_key": key,
            "available_net": available_net, "allocation_json": json.dumps(allocations),
        })
    decisions = {row.order: row for row in decide_dispatch(
        availability, run_date, flt(settings.minimum_net_value) or 150,
        int(settings.kindergarten_wait_days or 5), _holidays(settings)
    )}
    for row in rows:
        decision = decisions[row["sales_order"]]
        row.update(release=decision.release, reason=decision.reason, age_workdays=decision.age_workdays)
    return rows


def create_preview(mode="Manual", run_date=None):
    run = frappe.get_doc({
        "doctype": "Shipping Run", "status": "Preview", "mode": mode,
        "run_date": run_date or nowdate(), "started_by": frappe.session.user,
    })
    for row in analyse_open_orders(run.run_date):
        payload = dict(row)
        payload.pop("address_key", None)
        run.append("entries", payload)
    released = sum(1 for row in run.entries if row.release)
    run.summary = f"{len(run.entries)} offene Aufträge geprüft; {released} freigegeben."
    run.insert(ignore_permissions=mode == "Automatic")
    return run


def execute_shipping_run(mode="Manual", run_date=None):
    """Create grouped Pick Lists only; delivery notes wait for packing confirmation."""
    settings = frappe.get_single("Shipping Run Settings")
    if not settings.enabled:
        frappe.throw("Der Versandlauf ist in den Einstellungen nicht aktiviert.")
    run = create_preview(mode, run_date)
    run.status = "Running"
    run.save(ignore_permissions=mode == "Automatic")
    grouped = {}
    for entry in run.entries:
        if not entry.release:
            continue
        key = _address_key(frappe.db.get_value("Sales Order", entry.sales_order, "company"), entry.shipping_address)
        grouped.setdefault(key, []).append(entry)
    try:
        for entries in grouped.values():
            pick = _create_pick_list(run, entries, bool(settings.submit_pick_lists))
            for entry in entries:
                entry.pick_list = pick.name
        run.save(ignore_permissions=mode == "Automatic")
        run.status = "Pick Lists Created"
        run.summary += " Picklisten erstellt; Lieferscheine werden erst bei der Lagerbestätigung erzeugt."
        run.save(ignore_permissions=mode == "Automatic")
        frappe.db.commit()
    except Exception:
        run.db_set("status", "Failed", update_modified=False)
        frappe.log_error(frappe.get_traceback(), f"Versandlauf {run.name}")
        raise
    return run


def confirm_packing(run_name, pick_list_name, package_count, weights):
    """Create/submit DNs for one packed address group and then request GLS labels."""
    from brightsteps_gls.services.grouping import assign_delivery_note
    from brightsteps_gls.services.shipment import create_labels, set_weights

    frappe.db.sql("select name from `tabShipping Run` where name=%s for update", (run_name,))
    run = frappe.get_doc("Shipping Run", run_name)
    run.check_permission("write")
    if run.status not in ("Pick Lists Created", "Partially Dispatched", "Needs Review"):
        frappe.throw("Dieser Versandlauf ist nicht zur Lagerbestätigung bereit.")
    pick = frappe.get_doc("Pick List", pick_list_name)
    if pick.docstatus != 1:
        frappe.throw("Die Pickliste muss zuerst kontrolliert und eingereicht werden.")
    entries = [row for row in run.entries if row.pick_list == pick.name and row.release]
    if not entries:
        frappe.throw("Für diese Pickliste wurden keine freigegebenen Aufträge gefunden.")
    package_count = int(package_count or 0)
    weights = [flt(value) for value in weights]
    if package_count < 1 or package_count != len(weights) or any(value <= 0 for value in weights):
        frappe.throw("Paketanzahl und positive Paketgewichte müssen vollständig angegeben werden.")

    try:
        shipment_names = set()
        for entry in entries:
            if entry.delivery_note and frappe.db.exists("Delivery Note", entry.delivery_note):
                dn = frappe.get_doc("Delivery Note", entry.delivery_note)
            else:
                allocations = _picked_allocations(entry, pick)
                if not allocations:
                    frappe.throw(f"Für Auftrag {entry.sales_order} wurde keine Menge gepackt.")
                dn = _create_delivery_note(run, pick, entry, submit=True, allocations=allocations)
                entry.delivery_note = dn.name
            dn.db_set("custom_gls_paketanzahl", package_count, update_modified=False)
            shipment_names.add(assign_delivery_note(dn))
        if len(shipment_names) != 1:
            frappe.throw("Die Lieferscheine konnten nicht eindeutig einer gemeinsamen GLS-Sendung zugeordnet werden.")
        run.save()
        shipment_name = shipment_names.pop()
        set_weights(shipment_name, weights)
        result = create_labels(shipment_name)
        remaining = [row for row in run.entries if row.release and not row.delivery_note]
        run.status = "Partially Dispatched" if remaining else "Dispatched"
        run.summary = (run.summary or "") + f" {pick.name}: {len(entries)} Lieferschein(e) und {package_count} Paketschein(e) erzeugt."
        run.save()
        return {"run": run.name, "shipment": shipment_name, "delivery_notes": [row.delivery_note for row in entries], **result}
    except Exception:
        run.db_set("status", "Needs Review", update_modified=False)
        frappe.log_error(frappe.get_traceback(), f"Lagerbestätigung {run.name} / {pick.name}")
        raise


def _picked_allocations(entry, pick):
    planned = {row["sales_order_item"]: row for row in json.loads(entry.allocation_json)}
    confirmed = {}
    for row in pick.locations:
        if row.sales_order != entry.sales_order or not row.sales_order_item or flt(row.qty) <= 0:
            continue
        allocation = dict(planned.get(row.sales_order_item) or {})
        if not allocation:
            continue
        allocation["qty"] = min(flt(row.qty), flt(allocation["open_qty"]))
        confirmed[row.sales_order_item] = allocation
    return confirmed


def _create_pick_list(run, entries, submit):
    first_order = frappe.get_doc("Sales Order", entries[0].sales_order)
    pick = frappe.get_doc({
        "doctype": "Pick List", "company": first_order.company,
        "purpose": "Delivery", "items_based_on": "Sales Order",
        "group_same_items": 1, "custom_shipping_run": run.name, "locations": [],
    })
    for entry in entries:
        for item in json.loads(entry.allocation_json):
            if flt(item["qty"]) <= 0:
                continue
            pick.append("locations", {
                "item_code": item["item_code"], "qty": item["qty"],
                "stock_qty": item["qty"] * item["conversion_factor"],
                "conversion_factor": item["conversion_factor"], "warehouse": item["warehouse"],
                "sales_order": entry.sales_order, "sales_order_item": item["sales_order_item"],
            })
    pick.set_item_locations()
    pick.insert(ignore_permissions=True)
    if submit:
        pick.submit()
    return pick


def _create_delivery_note(run, pick, entry, submit, allocations=None):
    try:
        from erpnext.selling.doctype.sales_order.mapper import make_delivery_note
    except ImportError:  # ERPNext <= 15 compatibility
        from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note

    allocations = allocations or {
        row["sales_order_item"]: row for row in json.loads(entry.allocation_json) if flt(row["qty"]) > 0
    }
    dn = make_delivery_note(entry.sales_order)
    kept = []
    pick_rows = {row.sales_order_item: row for row in pick.locations if row.sales_order == entry.sales_order}
    for item in dn.items:
        allocation = allocations.get(item.so_detail)
        if not allocation:
            continue
        item.qty = allocation["qty"]
        item.stock_qty = allocation["qty"] * allocation["conversion_factor"]
        location = pick_rows.get(item.so_detail)
        if location:
            item.against_pick_list = pick.name
            item.pick_list_item = location.name
        kept.append(item)
    dn.set("items", kept)
    dn.custom_shipping_run = run.name
    dn.custom_backorder_snapshot = _backorder_snapshot(entry.sales_order, allocations)
    dn.insert(ignore_permissions=True)
    if submit:
        dn.submit()
    return dn


def _backorder_snapshot(order_name, allocations):
    order = frappe.get_doc("Sales Order", order_name)
    rows = []
    for item in order.items:
        remaining = max(0.0, flt(item.qty) - flt(item.delivered_qty) - flt(allocations.get(item.name, {}).get("qty")))
        if remaining:
            rows.append({"item_code": item.item_code, "item_name": item.item_name, "qty": remaining, "uom": item.uom})
    return json.dumps(rows, ensure_ascii=False)
