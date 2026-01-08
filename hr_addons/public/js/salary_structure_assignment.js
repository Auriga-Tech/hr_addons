frappe.ui.form.on('Salary Structure Assignment', {
    async employee(frm) {
        if (!frm.doc.employee) return;

        frappe.call({
            method: "hr_addons.hr_addons.overrides.salary_structure_assignment.get_overtime_rate",
            args: {
                employee: frm.doc.employee
            },
            callback: function(r) {
                if (r.message) {
                    frm.set_value("custom_ot_rate", r.message.hourly_rate);
                    frm.set_value("custom_ot_amount_calculation", r.message.overtime_amount_calculation);
                    frm.set_value("custom_standard_multiplier", r.message.standard_multiplier);
                    frm.refresh_fields();
                } 
            }
        });
    }
});

