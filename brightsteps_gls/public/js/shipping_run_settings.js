frappe.ui.form.on("Shipping Run Settings", {
  refresh(frm) {
    frm.add_custom_button(__("Nur Vorschau erstellen"), () => run("preview_shipping_run"));
    frm.add_custom_button(__("Versandlauf jetzt starten"), () => {
      frappe.confirm(
        __("Picklisten werden zuerst erstellt. Lieferscheine folgen nur für gebuchte Picklisten. Fortfahren?"),
        () => run("start_shipping_run")
      );
    }).addClass("btn-primary");

    function run(method) {
      frappe.call({
        method: `brightsteps_gls.api.${method}`,
        freeze: true,
        callback(r) {
          if (r.message && r.message.shipping_run) {
            frappe.set_route("Form", "Shipping Run", r.message.shipping_run);
          }
        },
      });
    }
  },
});
