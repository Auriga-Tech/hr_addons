# Copyright (c) 2025, Your Company and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document




@frappe.whitelist()
def get_overtime_rate(employee):

    #Get default shift from Employee
    default_shift = frappe.db.get_value("Employee", employee, "default_shift")
    if not default_shift:
        return None

    # Get overtime type from Shift Type
    overtime_type = frappe.db.get_value("Shift Type", default_shift, "custom_overtime_type")
    if not overtime_type:
        return None

    # Get standard multiplier from Overtime Type
    overtime_data = frappe.db.get_value(
        "Overtime Type",
        overtime_type,
        ["hourly_rate", "overtime_amount_calculation","standard_multiplier"],
        as_dict=True
    )

    return overtime_data
