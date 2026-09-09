import frappe

from brightsteps_gls.services.shipping_run import execute_shipping_run


def daily_shipping_run():
    settings = frappe.get_single("Shipping Run Settings")
    if settings.enabled and settings.automatic_run:
        execute_shipping_run(mode="Automatic")
