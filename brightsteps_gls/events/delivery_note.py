import frappe

from brightsteps_gls.services.grouping import assign_delivery_note


def on_update(doc, method=None):
    if doc.docstatus == 2 or doc.is_return or not int(doc.get("custom_gls_paketanzahl") or 0):
        return
    assign_delivery_note(doc)


def on_cancel(doc, method=None):
    shipment_name = doc.get("custom_gls_shipment")
    if not shipment_name or not frappe.db.exists("GLS Shipment", shipment_name):
        return
    shipment = frappe.get_doc("GLS Shipment", shipment_name)
    if shipment.status not in ("Draft", "Ready"):
        frappe.throw("Der Lieferschein gehört zu einer bereits bei GLS angelegten Sendung. Pakete zuerst in der GLS-Sendung klären.")
    shipment.set("delivery_notes", [row for row in shipment.delivery_notes if row.delivery_note != doc.name])
    if shipment.delivery_notes:
        shipment.save(ignore_permissions=True)
    else:
        frappe.delete_doc("GLS Shipment", shipment.name, ignore_permissions=True)

