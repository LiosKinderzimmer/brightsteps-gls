import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


FIELDS = {
    "Delivery Note": [
        {
            "fieldname": "custom_gls_section",
            "label": "GLS Versand",
            "fieldtype": "Section Break",
            "insert_after": "is_return",
            "collapsible": 1,
        },
        {
            "fieldname": "custom_gls_shipment",
            "label": "GLS Sendung",
            "fieldtype": "Link",
            "options": "GLS Shipment",
            "insert_after": "custom_gls_section",
            "read_only": 1,
            "no_copy": 1,
        },
        {
            "fieldname": "custom_gls_paketanzahl",
            "label": "GLS Paketanzahl",
            "fieldtype": "Int",
            "insert_after": "custom_gls_shipment",
            "non_negative": 1,
            "default": "0",
        },
        {
            "fieldname": "custom_gls_status",
            "label": "GLS Status",
            "fieldtype": "Data",
            "insert_after": "custom_gls_paketanzahl",
            "read_only": 1,
            "no_copy": 1,
        },
        {
            "fieldname": "custom_shipping_run",
            "label": "Versandlauf",
            "fieldtype": "Link",
            "options": "Shipping Run",
            "insert_after": "custom_gls_status",
            "read_only": 1,
            "no_copy": 1,
        },
        {
            "fieldname": "custom_backorder_snapshot",
            "label": "Rückstände nach dieser Lieferung",
            "fieldtype": "Long Text",
            "insert_after": "custom_shipping_run",
            "read_only": 1,
            "allow_on_submit": 1,
            "no_copy": 1,
        },
    ]
    ,
    "Pick List": [{
        "fieldname": "custom_shipping_run",
        "label": "Versandlauf",
        "fieldtype": "Link",
        "options": "Shipping Run",
        "insert_after": "purpose",
        "read_only": 1,
        "no_copy": 1,
    }],
}


def after_install():
    create_custom_fields(FIELDS, update=True)
    seed_settings()
    # A fresh installation must never create stock documents on its own.
    # An administrator enables each stage only after the TEST acceptance run.
    seed_shipping_run_settings(force_safe=True)
    seed_backorder_print_format()
    disable_legacy_scripts()


def after_migrate():
    create_custom_fields(FIELDS, update=True)
    seed_shipping_run_settings()
    seed_backorder_print_format()


def seed_settings():
    settings = frappe.get_single("GLS Settings")
    changed = False
    defaults = {
        "environment": "Sandbox",
        "sandbox_auth_url": "https://api-sandbox.gls-group.net/oauth2/v2/token",
        "sandbox_api_url": "https://api-sandbox.gls-group.net/shipit-farm/v1/backend",
        "production_auth_url": "https://api.gls-group.net/oauth2/v2/token",
        "production_api_url": "https://api.gls-group.net/shipit-farm/v1/backend",
        "group_same_address": 1,
        "test_email": "info@lioskinderzimmer.com",
    }
    for field, value in defaults.items():
        if not settings.get(field):
            settings.set(field, value)
            changed = True
    if changed:
        settings.save(ignore_permissions=True)


def seed_shipping_run_settings(force_safe=False):
    settings = frappe.get_single("Shipping Run Settings")
    defaults = {
        "enabled": 0,
        "automatic_run": 0,
        "minimum_net_value": 150,
        "kindergarten_wait_days": 5,
        "end_customer_group": "Endkunde",
        "kindergarten_group": "Kindergarten",
        "warning_days": 5,
        "critical_days": 8,
        "submit_pick_lists": 0,
        "submit_delivery_notes": 0,
    }
    changed = False
    for field, value in defaults.items():
        if force_safe and field in ("enabled", "automatic_run", "submit_pick_lists", "submit_delivery_notes"):
            settings.set(field, 0)
            changed = True
        elif settings.get(field) is None:
            settings.set(field, value)
            changed = True
    if changed:
        settings.save(ignore_permissions=True)


def seed_backorder_print_format():
    name = "Lieferschein mit Rückständen"
    html = """{% set backlog = frappe.parse_json(doc.custom_backorder_snapshot or '[]') %}
<h2>Lieferschein {{ doc.name }}</h2>
{{ doc.get_formatted('customer_name') or doc.customer_name }}
<table class=\"table table-bordered\"><thead><tr><th>Artikel</th><th>Bezeichnung</th><th>Menge</th></tr></thead><tbody>
{% for row in doc.items %}<tr><td>{{ row.item_code }}</td><td>{{ row.item_name }}</td><td>{{ row.qty }} {{ row.uom }}</td></tr>{% endfor %}
</tbody></table>
{% if backlog %}<h4>Noch offene Positionen aus diesem Auftrag</h4>
<table class=\"table table-bordered\"><thead><tr><th>Artikel</th><th>Bezeichnung</th><th>Rückstand</th></tr></thead><tbody>
{% for row in backlog %}<tr><td>{{ row.item_code }}</td><td>{{ row.item_name }}</td><td>{{ row.qty }} {{ row.uom }}</td></tr>{% endfor %}
</tbody></table>{% endif %}"""
    if frappe.db.exists("Print Format", name):
        frappe.db.set_value("Print Format", name, "html", html)
        return
    frappe.get_doc({
        "doctype": "Print Format", "name": name, "doc_type": "Delivery Note",
        "print_format_type": "Jinja", "custom_format": 1, "html": html,
    }).insert(ignore_permissions=True)


def disable_legacy_scripts():
    legacy = {
        "Client Script": ["GLS Sandbox Lieferschein"],
        "Server Script": [
            "GLS Sandbox Test",
            "GLS Sandbox Paketkorrektur",
            "GLS Sandbox Versandmail Prüfung",
            "GLS Sandbox Versandmail Zeitplan",
        ],
    }
    for doctype, names in legacy.items():
        for name in names:
            if frappe.db.exists(doctype, name):
                frappe.db.set_value(doctype, name, "disabled", 1, update_modified=False)
