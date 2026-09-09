import frappe

from brightsteps_gls.services.grouping import assign_delivery_note
from brightsteps_gls.services.shipment import cancel_parcel, create_labels, refresh_tracking, replace_parcel, set_weights
from brightsteps_gls.services.shipping_run import confirm_packing, create_preview, execute_shipping_run


@frappe.whitelist()
def prepare_delivery_note(delivery_note):
    doc = frappe.get_doc("Delivery Note", delivery_note)
    doc.check_permission("write")
    return {"shipment": assign_delivery_note(doc)}


@frappe.whitelist()
def save_weights(shipment, weights):
    values = frappe.parse_json(weights)
    doc = set_weights(shipment, values)
    return {"ok": True, "shipment": doc.name}


@frappe.whitelist()
def request_labels(shipment):
    return create_labels(shipment)


@frappe.whitelist()
def cancel_package(shipment, track_id):
    return cancel_parcel(shipment, track_id)


@frappe.whitelist()
def replace_package(shipment, track_id, weight):
    return replace_parcel(shipment, track_id, weight)


@frappe.whitelist()
def check_tracking(shipment):
    doc = refresh_tracking(shipment)
    return {"ok": True, "status": doc.status, "checked_at": doc.last_tracking_check}


@frappe.whitelist()
def preview_shipping_run(run_date=None):
    doc = create_preview(run_date=run_date)
    return {"ok": True, "shipping_run": doc.name, "summary": doc.summary}


@frappe.whitelist()
def start_shipping_run(run_date=None):
    doc = execute_shipping_run(run_date=run_date)
    return {"ok": True, "shipping_run": doc.name, "status": doc.status, "summary": doc.summary}


@frappe.whitelist()
def confirm_packed_pick_list(shipping_run, pick_list, package_count, weights):
    values = frappe.parse_json(weights)
    return confirm_packing(shipping_run, pick_list, package_count, values)
