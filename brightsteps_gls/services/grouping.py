import json
import re

import frappe
from frappe.utils import getdate

from brightsteps_gls.services.domain import build_grouping_key, common_package_count


OPEN_GROUPING_STATUSES = ("Draft", "Ready")


def split_street(value):
    parts = (value or "").strip().rsplit(" ", 1)
    if len(parts) != 2 or not parts[0] or not parts[1] or not parts[1][0].isdigit():
        frappe.throw("Straße und Hausnummer müssen in Adresszeile 1 eindeutig angegeben sein.")
    return parts


def address_snapshot(delivery_note):
    address_name = delivery_note.shipping_address_name or delivery_note.customer_address
    if not address_name:
        frappe.throw("Für den GLS-Versand fehlt eine Liefer- oder Rechnungsadresse.")
    address = frappe.get_doc("Address", address_name)
    if address.disabled:
        frappe.throw("Die ausgewählte Versandadresse ist deaktiviert.")
    country_code = (frappe.db.get_value("Country", address.country, "code") or "").upper()
    street, number = split_street(address.address_line1)
    snapshot = {
        "address_name": address.name,
        "name": delivery_note.customer_name or address.address_title,
        "name2": address.address_line2 or "",
        "country_code": country_code,
        "postal_code": address.pincode or "",
        "city": address.city or "",
        "street": street,
        "street_number": number,
        "email": address.email_id or "",
    }
    for field in ("name", "country_code", "postal_code", "city", "street", "street_number"):
        if not snapshot[field]:
            frappe.throw(f"In der Versandadresse fehlt: {field}.")
    return snapshot


def grouping_key(company, shipping_date, snapshot):
    return build_grouping_key(company, getdate(shipping_date), snapshot)


def assign_delivery_note(delivery_note):
    settings = frappe.get_single("GLS Settings")
    if not settings.enabled:
        return None
    snapshot = address_snapshot(delivery_note)
    key = grouping_key(delivery_note.company, delivery_note.posting_date, snapshot)
    if not settings.group_same_address:
        key = grouping_key(delivery_note.company, delivery_note.posting_date, dict(snapshot, name=snapshot["name"] + " " + delivery_note.name))
    current = delivery_note.get("custom_gls_shipment")
    if current:
        shipment = frappe.get_doc("GLS Shipment", current)
        if shipment.grouping_key != key:
            frappe.throw("Die Versandadresse oder das Versanddatum wurde geändert. Den bestehenden GLS-Versand zuerst auflösen.")
        existing_row = next((row for row in shipment.delivery_notes if row.delivery_note == delivery_note.name), None)
        requested_count = int(delivery_note.get("custom_gls_paketanzahl") or 0)
        if shipment.status not in OPEN_GROUPING_STATUSES and existing_row and int(existing_row.package_count or 0) != requested_count:
            frappe.throw("Die gemeinsame GLS-Sendung wurde bereits geschlossen. Die Paketanzahl kann nur über die Paketkorrektur geändert werden.")
    else:
        shipment_name = frappe.db.get_value(
            "GLS Shipment",
            {"open_grouping_key": key, "status": ["in", OPEN_GROUPING_STATUSES]},
            "name",
            order_by="creation asc",
        )
        if shipment_name:
            shipment = frappe.get_doc("GLS Shipment", shipment_name)
        else:
            shipment = frappe.new_doc("GLS Shipment")
            shipment.environment = settings.environment
            shipment.company = delivery_note.company
            shipment.shipping_date = delivery_note.posting_date
            shipment.customer = delivery_note.customer
            shipment.shipping_address = snapshot["address_name"]
            shipment.address_snapshot = json.dumps(snapshot, ensure_ascii=False, sort_keys=True)
            shipment.grouping_key = key
            shipment.open_grouping_key = key
            shipment.status = "Draft"
    if not any(row.delivery_note == delivery_note.name for row in shipment.delivery_notes):
        shipment.append("delivery_notes", {
            "delivery_note": delivery_note.name,
            "customer": delivery_note.customer,
            "package_count": int(delivery_note.get("custom_gls_paketanzahl") or 0),
        })
    else:
        for row in shipment.delivery_notes:
            if row.delivery_note == delivery_note.name:
                row.package_count = int(delivery_note.get("custom_gls_paketanzahl") or 0)
    # Every linked delivery note displays the package count for the common
    # consignment. It is therefore the maximum, never the sum of the rows.
    shipment.desired_package_count = common_package_count(row.package_count for row in shipment.delivery_notes)
    try:
        shipment.save(ignore_permissions=True)
    except frappe.DuplicateEntryError:
        # A second worker created the same open group concurrently. Join the
        # unique winner instead of leaving duplicate shipping records.
        existing_name = frappe.db.get_value("GLS Shipment", {"open_grouping_key": key}, "name")
        if not existing_name:
            raise
        shipment = frappe.get_doc("GLS Shipment", existing_name)
        if not any(row.delivery_note == delivery_note.name for row in shipment.delivery_notes):
            shipment.append("delivery_notes", {
                "delivery_note": delivery_note.name,
                "customer": delivery_note.customer,
                "package_count": int(delivery_note.get("custom_gls_paketanzahl") or 0),
            })
        shipment.desired_package_count = common_package_count(row.package_count for row in shipment.delivery_notes)
        shipment.save(ignore_permissions=True)
    if delivery_note.get("custom_gls_shipment") != shipment.name:
        delivery_note.db_set("custom_gls_shipment", shipment.name, update_modified=False)
    return shipment.name
