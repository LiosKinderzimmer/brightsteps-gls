import json

import frappe

from brightsteps_gls.services.shipping_run import analyse_open_orders


def execute(filters=None):
    filters = frappe._dict(filters or {})
    settings = frappe.get_single("Shipping Run Settings")
    warning, critical = int(settings.warning_days or 5), int(settings.critical_days or 8)
    data = []
    for row in analyse_open_orders(filters.run_date):
        allocations = json.loads(row["allocation_json"])
        missing = [f'{item["item_code"]}: {item["open_qty"] - item["qty"]:g}' for item in allocations if item["open_qty"] > item["qty"]]
        age = row["age_workdays"]
        status = "Dunkelrot" if age >= critical + 5 else "Rot" if age >= critical else "Gelb" if age >= warning else "Grün"
        data.append({
            "sales_order": row["sales_order"], "customer": row["customer"],
            "customer_group": row["customer_group"], "shipping_address": row["shipping_address"],
            "age_workdays": age, "available_net": row["available_net"],
            "release": row["release"], "reason": row["reason"], "missing_items": ", ".join(missing),
            "status": status,
        })
    columns = [
        {"fieldname":"status","label":"Ampel","fieldtype":"Data","width":85},
        {"fieldname":"sales_order","label":"Auftrag","fieldtype":"Link","options":"Sales Order","width":150},
        {"fieldname":"customer","label":"Kunde","fieldtype":"Link","options":"Customer","width":170},
        {"fieldname":"customer_group","label":"Kundengruppe","fieldtype":"Data","width":130},
        {"fieldname":"age_workdays","label":"Werktage","fieldtype":"Int","width":85},
        {"fieldname":"available_net","label":"Verfügbar netto","fieldtype":"Currency","width":120},
        {"fieldname":"release","label":"Freigabe","fieldtype":"Check","width":80},
        {"fieldname":"reason","label":"Entscheidung","fieldtype":"Data","width":260},
        {"fieldname":"missing_items","label":"Fehlende Artikel / Menge","fieldtype":"Data","width":280},
        {"fieldname":"shipping_address","label":"Lieferadresse","fieldtype":"Link","options":"Address","width":170},
    ]
    return columns, data
