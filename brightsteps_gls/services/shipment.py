import json
import uuid

import frappe
from frappe.utils import now_datetime, today

from brightsteps_gls.services.gls_client import GLSClient, HANDED_OVER_STATUSES, SUCCESSFUL_CANCELLATIONS


def _lock(name):
    frappe.db.sql("select name from `tabGLS Shipment` where name=%s for update", (name,))
    return frappe.get_doc("GLS Shipment", name)


def _recipient(shipment):
    data = json.loads(shipment.address_snapshot)
    lines = [data["name"]]
    if data.get("name2"):
        lines.append(data["name2"])
    if len(lines) > 3 or any(len(line) > 40 for line in lines):
        frappe.throw("Empfängername oder Adresszusatz ist für GLS zu lang.")
    result = {
        "Name1": lines[0], "CountryCode": data["country_code"],
        "ZIPCode": data["postal_code"], "City": data["city"],
        "Street": data["street"], "StreetNumber": data["street_number"],
    }
    if len(lines) > 1:
        result["Name2"] = lines[1]
    if data.get("email"):
        result["eMail"] = data["email"]
    return result


def _payload(shipment, parcels):
    refs = [shipment.name] + [row.delivery_note for row in shipment.delivery_notes]
    settings = frappe.get_single("GLS Settings")
    contact_id = settings.production_contact_id if settings.environment == "Production" else settings.sandbox_contact_id
    if not contact_id:
        frappe.throw("GLS-Kundennummer für die gewählte Umgebung fehlt.")
    return {
        "ShipmentReference": refs,
        "Product": "PARCEL",
        "Shipper": {"ContactID": contact_id},
        "Consignee": {"Address": _recipient(shipment)},
        "ShipmentUnit": [
            {"Weight": parcel.weight, "ShipmentUnitReference": [f"{shipment.name}-P{parcel.idx}"]}
            for parcel in parcels
        ],
    }


def set_weights(shipment_name, weights):
    shipment = _lock(shipment_name)
    shipment.check_permission("write")
    weights = [float(value) for value in weights]
    if len(weights) != int(shipment.desired_package_count or 0) or any(value <= 0 for value in weights):
        frappe.throw("Für jedes Paket der gemeinsamen Sendung ist ein Gewicht größer als 0 erforderlich.")
    existing = [row for row in shipment.parcels if row.active]
    for index, parcel in enumerate(existing):
        if parcel.track_id and parcel.weight != weights[index]:
            frappe.throw(f"Paket {index + 1} hat bereits ein Label. Bitte die Paketkorrektur verwenden.")
    while len(existing) < len(weights):
        existing.append(shipment.append("parcels", {"active": 1, "status": "Draft"}))
    for index, weight in enumerate(weights):
        existing[index].weight = weight
    shipment.status = "Ready"
    shipment.save()
    return shipment


def create_labels(shipment_name):
    shipment = _lock(shipment_name)
    shipment.check_permission("write")
    if shipment.pending_operation:
        frappe.throw("Ein früherer GLS-Vorgang ist ungeklärt. Keine automatische Wiederholung.")
    active = [row for row in shipment.parcels if row.active]
    new = [row for row in active if not row.track_id]
    if len(active) != int(shipment.desired_package_count or 0):
        frappe.throw("Paketanzahl und Gewichte sind noch nicht vollständig.")
    if not new:
        return {"ok": True, "reused": True, "message": "Alle Paketscheine sind bereits vorhanden."}
    payload = _payload(shipment, new)
    client = GLSClient()
    valid, details = client.validate(payload)
    if not valid:
        frappe.throw("GLS hat die Versanddaten abgelehnt: " + json.dumps(details, ensure_ascii=False)[:1000])
    operation = {"id": str(uuid.uuid4()), "type": "create", "parcel_rows": [row.name for row in new], "started_at": str(now_datetime())}
    shipment.db_set("pending_operation", json.dumps(operation), update_modified=False)
    # Close the group before contacting GLS. A concurrently saved delivery note
    # must never join a shipment whose external creation may already have begun.
    shipment.db_set("open_grouping_key", None, update_modified=False)
    frappe.db.commit()
    shipment = _lock(shipment_name)
    created = client.create(payload)
    parcel_data = created.get("ParcelData") or []
    encoded_pdfs = []
    for item in created.get("PrintData") or []:
        if item.get("LabelFormat") == "PDF":
            data = item.get("Data")
            encoded_pdfs.extend(data if isinstance(data, list) else [data])
    if len(parcel_data) != len(new) or len(encoded_pdfs) != len(new):
        shipment.db_set("status", "Needs Review", update_modified=False)
        shipment.db_set("last_error", "GLS-Antwort enthält keine eindeutige Zuordnung zwischen Paketen und PDFs.", update_modified=False)
        frappe.db.commit()
        frappe.throw("GLS-Antwort muss geprüft werden. Es wird nicht erneut angefordert.")
    for row, remote, encoded in zip(new, parcel_data, encoded_pdfs):
        if not encoded or not encoded.startswith("JVBERi0") or not remote.get("TrackID") or not remote.get("ParcelNumber"):
            frappe.throw("GLS-Antwort enthält unvollständige Paketdaten. Keine Wiederholung ausführen.")
        filename = f"GLS-{shipment.environment.upper()}-{shipment.name}-P{row.idx}.pdf"
        file_doc = frappe.get_doc({
            "doctype": "File", "file_name": filename, "is_private": 1,
            "attached_to_doctype": "GLS Shipment", "attached_to_name": shipment.name,
            "content": encoded, "decode": True,
        }).insert()
        target = next(parcel for parcel in shipment.parcels if parcel.name == row.name)
        target.track_id = remote["TrackID"]
        target.parcel_number = remote["ParcelNumber"]
        target.label = file_doc.file_url
        target.status = "Label Created"
    shipment.pending_operation = ""
    shipment.status = "Label Created"
    shipment.last_error = ""
    shipment.save()
    _update_delivery_notes(shipment)
    return {"ok": True, "reused": False, "labels": [row.label for row in shipment.parcels if row.active], "message": f"{len(new)} Paketschein(e) gespeichert."}


def cancel_parcel(shipment_name, track_id):
    shipment = _lock(shipment_name)
    shipment.check_permission("write")
    if shipment.pending_operation:
        frappe.throw("Ein früherer GLS-Vorgang ist ungeklärt.")
    parcel = next((row for row in shipment.parcels if row.active and row.track_id == track_id), None)
    if not parcel:
        frappe.throw("Aktives Paket nicht gefunden.")
    operation = {"id": str(uuid.uuid4()), "type": "cancel", "track_id": track_id, "started_at": str(now_datetime())}
    shipment.db_set("pending_operation", json.dumps(operation), update_modified=False)
    frappe.db.commit()
    returned_id, result = GLSClient().cancel(track_id)
    shipment = _lock(shipment_name)
    parcel = next(row for row in shipment.parcels if row.track_id == track_id)
    parcel.cancel_result = result
    if returned_id != track_id or result not in SUCCESSFUL_CANCELLATIONS:
        shipment.status = "Needs Review" if result != "SCANNED" else "Shipped"
        shipment.last_error = f"GLS-Storno nicht bestätigt: {result or 'keine Antwort'}"
        shipment.pending_operation = ""
        shipment.save()
        frappe.db.commit()
        frappe.throw("GLS konnte dieses Paket nicht stornieren. Vorhandener Paketschein bleibt zugeordnet.")
    parcel.active = 0
    parcel.status = "Cancelled" if result == "CANCELLED" else "Cancellation Pending"
    shipment.pending_operation = ""
    shipment.status = "Label Created" if any(row.active for row in shipment.parcels) else "Cancelled"
    shipment.save()
    _update_delivery_notes(shipment)
    return {"ok": True, "message": "Das ausgewählte Paket wurde storniert. Alle anderen Paketscheine bleiben bestehen."}


def replace_parcel(shipment_name, track_id, weight):
    weight = float(weight)
    if weight <= 0:
        frappe.throw("Das neue Paketgewicht muss größer als 0 sein.")
    shipment = _lock(shipment_name)
    shipment.check_permission("write")
    old = next((row for row in shipment.parcels if row.active and row.track_id == track_id), None)
    if not old:
        frappe.throw("Aktives Paket nicht gefunden.")
    probe = frappe._dict(weight=weight, idx=len(shipment.parcels) + 1)
    valid, details = GLSClient().validate(_payload(shipment, [probe]))
    if not valid:
        frappe.throw("GLS hat die neuen Paketdaten abgelehnt: " + json.dumps(details, ensure_ascii=False)[:1000])
    cancelled = cancel_parcel(shipment_name, track_id)
    shipment = _lock(shipment_name)
    shipment.append("parcels", {
        "weight": weight, "active": 1, "status": "Draft",
        "source_delivery_note": old.source_delivery_note,
    })
    shipment.status = "Ready"
    shipment.save()
    created = create_labels(shipment_name)
    created["message"] = cancelled["message"] + " Ein neuer Paketschein wurde gespeichert."
    return created


def refresh_tracking(shipment_name):
    shipment = _lock(shipment_name)
    client = GLSClient()
    units = client.tracking(shipment.name, shipment.shipping_date, today())
    by_id = {item.get("TrackID"): item for item in units if item.get("TrackID")}
    active = [row for row in shipment.parcels if row.active and row.track_id]
    for parcel in active:
        unit = by_id.get(parcel.track_id)
        if not unit:
            continue
        status = unit.get("Status") or ""
        parcel.status = {
            "DATA_RECEIVED": "Data Received", "PICKUP": "Picked Up", "HUB": "In Transit",
            "IN_DELIVERY": "Out For Delivery", "DELIVERED": "Delivered",
        }.get(status, parcel.status)
    statuses = [row.status for row in active]
    if statuses and all(status == "Delivered" for status in statuses):
        shipment.status = "Delivered"
    elif statuses and all(status in ("Picked Up", "In Transit", "Out For Delivery", "Delivered") for status in statuses):
        shipment.status = "Shipped"
    elif any(status in ("Picked Up", "In Transit", "Out For Delivery", "Delivered") for status in statuses):
        shipment.status = "Partially Handed Over"
    shipment.last_tracking_check = now_datetime()
    shipment.save()
    _update_delivery_notes(shipment)
    return shipment


def _update_delivery_notes(shipment):
    for row in shipment.delivery_notes:
        if frappe.db.exists("Delivery Note", row.delivery_note):
            frappe.db.set_value("Delivery Note", row.delivery_note, {
                "custom_gls_shipment": shipment.name, "custom_gls_status": shipment.status,
            }, update_modified=False)
