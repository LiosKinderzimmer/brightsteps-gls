import json
from html import escape

import frappe
from frappe.utils import now_datetime

from brightsteps_gls.services.shipment import refresh_tracking


def check_open_shipments():
    names = frappe.get_all(
        "GLS Shipment",
        filters={"status": ["in", ["Label Created", "Partially Handed Over", "Shipped"]]},
        pluck="name",
    )
    for name in names:
        try:
            shipment = refresh_tracking(name)
            if shipment.status in ("Shipped", "Delivered"):
                queue_dispatch_email(shipment)
            frappe.db.commit()
        except Exception:
            frappe.db.rollback()
            frappe.log_error("GLS-Statusprüfung fehlgeschlagen", f"GLS Shipment {name}")


def queue_dispatch_email(shipment):
    notified = set(json.loads(shipment.notified_track_ids or "[]"))
    ready = [
        row for row in shipment.parcels
        if row.active and row.track_id and row.status in ("Picked Up", "In Transit", "Out For Delivery", "Delivered") and row.track_id not in notified
    ]
    if not ready:
        return
    settings = frappe.get_single("GLS Settings")
    snapshot = json.loads(shipment.address_snapshot)
    recipient = settings.test_email if settings.environment == "Sandbox" else snapshot.get("email")
    if not recipient:
        shipment.last_error = "Keine E-Mail-Adresse für die Versandbestätigung vorhanden."
        shipment.save(ignore_permissions=True)
        return
    refs = ", ".join(row.delivery_note for row in shipment.delivery_notes)
    links = "".join(
        f'<li><a href="https://gls-group.eu/AT/de/paket-verfolgen?match={row.parcel_number}">{row.parcel_number}</a></li>'
        for row in ready if (row.parcel_number or "").isalnum()
    )
    if not links:
        return
    prefix = "[GLS SANDBOX TEST] " if settings.environment == "Sandbox" else ""
    message = (
        ("<p><strong>Interner Sandbox-Test – keine echte Versandbestätigung.</strong></p>" if settings.environment == "Sandbox" else "")
        + f"<p>Guten Tag,</p><p>Ihre Lieferung zu den Lieferscheinen {escape(refs)} wurde an GLS übergeben.</p>"
        + f"<p>Paketverfolgung:</p><ul>{links}</ul><p>Freundliche Grüße<br>Bright Steps</p>"
    )
    mail = frappe.sendmail(
        recipients=[recipient], subject=f"{prefix}Ihre Lieferung {shipment.name}", message=message,
        reference_doctype="GLS Shipment", reference_name=shipment.name,
        delayed=True, now=False, add_unsubscribe_link=0,
    )
    if not mail or not mail.name:
        frappe.throw("Die Versandmail konnte nicht in die Warteschlange gestellt werden.")
    notified.update(row.track_id for row in ready)
    shipment.notified_track_ids = json.dumps(sorted(notified))
    shipment.email_sent_at = now_datetime()
    shipment.save(ignore_permissions=True)
