function editWeights(frm) {
  const count = Number(frm.doc.desired_package_count || 0);
  if (!Number.isInteger(count) || count < 1 || count > 99) {
    frappe.msgprint(__("Bitte eine Paketanzahl zwischen 1 und 99 eintragen."));
    return;
  }
  const active = (frm.doc.parcels || []).filter(row => row.active);
  const fields = Array.from({length: count}, (_, index) => ({
    fieldname: `weight_${index}`,
    fieldtype: "Float",
    label: __("Paket {0} – Gewicht (kg)", [index + 1]),
    default: active[index]?.weight,
    read_only: Boolean(active[index]?.track_id),
    reqd: 1,
  }));
  const dialog = new frappe.ui.Dialog({
    title: __("Gewichte der gemeinsamen Sendung"),
    fields,
    primary_action_label: __("Gewichte speichern"),
    async primary_action(values) {
      const weights = Array.from({length: count}, (_, index) => Number(values[`weight_${index}`]));
      if (weights.some(value => !Number.isFinite(value) || value <= 0)) {
        frappe.msgprint(__("Für jedes Paket ist ein Gewicht größer als 0 erforderlich."));
        return;
      }
      await frappe.call({
        method: "brightsteps_gls.api.save_weights",
        args: {shipment: frm.doc.name, weights: JSON.stringify(weights)},
        freeze: true,
      });
      dialog.hide();
      await frm.reload_doc();
    },
  });
  dialog.show();
}

function manageParcel(frm) {
  const parcels = (frm.doc.parcels || []).filter(row => row.active && row.track_id);
  if (!parcels.length) {
    frappe.msgprint(__("Es gibt noch keine aktiven Paketscheine."));
    return;
  }
  const dialog = new frappe.ui.Dialog({
    title: __("Einzelnes Paket korrigieren oder entfernen"),
    fields: [
      {fieldname: "track_id", fieldtype: "Select", label: __("Paket"), reqd: 1,
        options: parcels.map(row => ({label: `${row.parcel_number} · ${row.weight} kg`, value: row.track_id}))},
      {fieldname: "operation", fieldtype: "Select", label: __("Änderung"), reqd: 1,
        options: `${__("Gewicht korrigieren")}\n${__("Paket entfernen")}`},
      {fieldname: "weight", fieldtype: "Float", label: __("Neues Gewicht (kg)"),
        depends_on: `eval:doc.operation=="${__("Gewicht korrigieren")}"`},
    ],
    primary_action_label: __("Änderung ausführen"),
    primary_action(values) {
      const remove = values.operation === __("Paket entfernen");
      if (!remove && !(Number(values.weight) > 0)) {
        frappe.msgprint(__("Bitte das neue Gewicht eingeben."));
        return;
      }
      frappe.confirm(
        remove
          ? __("Dieses Paket bei GLS stornieren? Alle anderen Paketscheine bleiben bestehen.")
          : __("Dieses Paket stornieren und einen Paketschein mit dem neuen Gewicht erstellen?"),
        async () => {
          dialog.hide();
          const response = await frappe.call({
            method: remove ? "brightsteps_gls.api.cancel_package" : "brightsteps_gls.api.replace_package",
            args: {shipment: frm.doc.name, track_id: values.track_id, weight: values.weight},
            freeze: true,
            freeze_message: __("GLS-Paket wird geprüft …"),
          });
          await frm.reload_doc();
          frappe.msgprint(response.message.message);
        }
      );
    },
  });
  dialog.show();
}

frappe.ui.form.on("GLS Shipment", {
  refresh(frm) {
    if (frm.is_new()) return;
    if (["Draft", "Ready", "Label Created"].includes(frm.doc.status)) {
      frm.add_custom_button(__("Paketgewichte eingeben"), () => editWeights(frm), __("GLS"));
    }
    if (["Ready", "Label Created"].includes(frm.doc.status)) {
      frm.add_custom_button(__("Paketscheine erstellen"), async () => {
        const response = await frappe.call({
          method: "brightsteps_gls.api.request_labels", args: {shipment: frm.doc.name},
          freeze: true, freeze_message: __("GLS-Paketscheine werden erstellt …"),
        });
        await frm.reload_doc();
        frappe.msgprint(response.message.message);
      }, __("GLS"));
    }
    if ((frm.doc.parcels || []).some(row => row.active && row.track_id)) {
      frm.add_custom_button(__("Paket korrigieren oder entfernen"), () => manageParcel(frm), __("GLS"));
      frm.add_custom_button(__("Sendungsstatus prüfen"), async () => {
        const response = await frappe.call({method: "brightsteps_gls.api.check_tracking", args: {shipment: frm.doc.name}, freeze: true});
        await frm.reload_doc();
        frappe.show_alert(__("GLS-Status: {0}", [response.message.status]));
      }, __("GLS"));
    }
  },
});

