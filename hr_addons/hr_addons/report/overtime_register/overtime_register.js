// Copyright (c) 2025, Auriga IT and contributors
// For license information, please see license.txt
frappe.query_reports["Overtime Register"] = {
    "filters": [
       {
		    "fieldname": "from_date",
		    "label": "From Date",
		    "fieldtype": "Date",
		    "reqd": 1
		},
		{
		    "fieldname": "to_date",
		    "label": "To Date",
		    "fieldtype": "Date",
		    "reqd": 1
		},
        {
            "fieldname": "employee",
            "label": "Employee",
            "fieldtype": "Link",
            "options": "Employee"
        },

        {
            "fieldname": "department",
            "label": "Department",
            "fieldtype": "Link",
            "options": "Department"
        },
        {
            "fieldname": "designation",
            "label": __("Primary Designation"),
            "fieldtype": "MultiSelectList",
            "get_data": function(txt) {
                return frappe.db.get_link_options("Designation", txt);
            }
        },
        {
            fieldname: "employment_type",
            label: __("Employment Type"),
            fieldtype: "MultiSelectList",
            get_data: function(txt) {
                return frappe.db.get_link_options("Employment Type", txt);
            }
        }
    ],
    formatter: function (value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        if (column.fieldname === "employee" && data && data.employee) {
            const from_date = frappe.query_report.get_filter_value("from_date");
            const to_date = frappe.query_report.get_filter_value("to_date");

            const route = `/app/query-report/Overtime Detail Report?employee=${data.employee}&from_date=${from_date}&to_date=${to_date}`;
            return `<a href="${route}" target="_blank">${value}</a>`;
        }

        return value;
    }
};
