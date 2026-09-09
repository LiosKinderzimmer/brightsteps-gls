app_name = "brightsteps_gls"
app_title = "Bright Steps GLS"
app_publisher = "Bright Steps"
app_description = "GLS ShipIT integration for grouped ERPNext deliveries"
app_email = "info@brightsteps.at"
app_license = "MIT"
app_version = "0.3.1"
required_apps = ["erpnext"]

after_install = "brightsteps_gls.setup.install.after_install"
after_migrate = "brightsteps_gls.setup.install.after_migrate"

doctype_js = {
    "Delivery Note": "public/js/delivery_note.js",
    "GLS Shipment": "public/js/gls_shipment.js",
    "Shipping Run": "public/js/shipping_run.js",
    "Shipping Run Settings": "public/js/shipping_run_settings.js",
}

doc_events = {
    "Delivery Note": {
        "on_update": "brightsteps_gls.events.delivery_note.on_update",
        "on_cancel": "brightsteps_gls.events.delivery_note.on_cancel",
    }
}

scheduler_events = {
    "cron": {
        "0 7 * * *": ["brightsteps_gls.jobs.shipping_run.daily_shipping_run"],
        "0 12,18 * * *": ["brightsteps_gls.jobs.tracking.check_open_shipments"],
    }
}
