frappe.query_reports["Shipping Backlog Monitor"] = {
  filters: [{fieldname: "run_date", label: __("Prüfdatum"), fieldtype: "Date", default: frappe.datetime.get_today()}],
  formatter(value, row, column, data, default_formatter) {
    value = default_formatter(value, row, column, data);
    if (column.fieldname === "status" && data) {
      const colors = {Grün: "green", Gelb: "orange", Rot: "red", Dunkelrot: "darkred"};
      value = `<span style="color:${colors[data.status] || "inherit"};font-weight:600">${value}</span>`;
    }
    return value;
  }
};
