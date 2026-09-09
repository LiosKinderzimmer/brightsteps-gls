function confirmPackedPickList(frm, pickList) {
  const first = new frappe.ui.Dialog({
    title: __("Versand bestätigen – {0}", [pickList]),
    fields: [{fieldname: "package_count", fieldtype: "Int", label: __("Paketanzahl"), reqd: 1, default: 1}],
    primary_action_label: __("Gewichte eingeben"),
    primary_action(values) {
      const count = Number(values.package_count || 0);
      if (!Number.isInteger(count) || count < 1 || count > 99) {
        frappe.msgprint(__("Bitte eine Paketanzahl zwischen 1 und 99 eingeben."));
        return;
      }
      first.hide();
      const weights = new frappe.ui.Dialog({
        title: __("Gepackte Sendung bestätigen"),
        fields: Array.from({length: count}, (_, index) => ({
          fieldname: `weight_${index}`, fieldtype: "Float",
          label: __("Paket {0} – Gewicht (kg)", [index + 1]), reqd: 1,
        })),
        primary_action_label: __("Lieferscheine und Paketscheine erstellen"),
        primary_action(data) {
          const values = Array.from({length: count}, (_, index) => Number(data[`weight_${index}`]));
          if (values.some(value => !Number.isFinite(value) || value <= 0)) {
            frappe.msgprint(__("Für jedes Paket ist ein Gewicht größer als 0 erforderlich."));
            return;
          }
          frappe.confirm(
            __("Die gepackten Mengen bestätigen, die einzelnen Lieferscheine buchen und anschließend die GLS-Paketscheine erstellen?"),
            async () => {
              weights.hide();
              const response = await frappe.call({
                method: "brightsteps_gls.api.confirm_packed_pick_list",
                args: {shipping_run: frm.doc.name, pick_list: pickList, package_count: count, weights: JSON.stringify(values)},
                freeze: true,
                freeze_message: __("Lieferscheine und GLS-Paketscheine werden erstellt …"),
              });
              await frm.reload_doc();
              frappe.msgprint(response.message.message || __("Versand wurde erstellt."));
            }
          );
        },
      });
      weights.show();
    },
  });
  first.show();
}

frappe.ui.form.on("Shipping Run", {
  refresh(frm) {
    if (frm.is_new() || !["Pick Lists Created", "Partially Dispatched", "Needs Review"].includes(frm.doc.status)) return;
    const pending = [...new Set((frm.doc.entries || []).filter(row => row.release && row.pick_list && !row.delivery_note).map(row => row.pick_list))];
    pending.forEach(pickList => {
      frm.add_custom_button(__("Versand bestätigen: {0}", [pickList]), () => confirmPackedPickList(frm, pickList), __("Lager"));
    });
  },
});
