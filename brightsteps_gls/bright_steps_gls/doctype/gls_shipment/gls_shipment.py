import json

import frappe
from frappe.model.document import Document


class GLSShipment(Document):
    def validate(self):
        if not self.delivery_notes:
            frappe.throw("Eine GLS-Sendung benötigt mindestens einen Lieferschein.")
        names = [row.delivery_note for row in self.delivery_notes]
        if len(names) != len(set(names)):
            frappe.throw("Ein Lieferschein darf nur einmal enthalten sein.")
        if any((row.package_count or 0) < 0 for row in self.delivery_notes):
            frappe.throw("Die Paketanzahl darf nicht negativ sein.")
        for parcel in self.parcels:
            if parcel.active and not (parcel.weight or 0) > 0:
                frappe.throw("Jedes aktive Paket benötigt ein Gewicht größer als 0.")
        if self.address_snapshot:
            json.loads(self.address_snapshot)

