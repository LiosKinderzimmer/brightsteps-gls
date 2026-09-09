frappe.ui.form.on("Delivery Note", {
  refresh(frm) {
    if (frm.is_new() || frm.doc.docstatus === 2 || frm.doc.is_return) return;
    if (frm.doc.custom_gls_shipment) {
      frm.add_custom_button(__("Gemeinsame GLS-Sendung öffnen"), () => {
        frappe.set_route("Form", "GLS Shipment", frm.doc.custom_gls_shipment);
      }, __("GLS Versand"));
    } else if (Number(frm.doc.custom_gls_paketanzahl || 0) > 0) {
      frm.add_custom_button(__("GLS-Sendung vorbereiten"), async () => {
        const response = await frappe.call({
          method: "brightsteps_gls.api.prepare_delivery_note",
          args: {delivery_note: frm.doc.name},
          freeze: true,
          freeze_message: __("Gemeinsame GLS-Sendung wird vorbereitet …"),
        });
        await frm.reload_doc();
        frappe.set_route("Form", "GLS Shipment", response.message.shipment);
      }, __("GLS Versand"));
    }
  },
});

