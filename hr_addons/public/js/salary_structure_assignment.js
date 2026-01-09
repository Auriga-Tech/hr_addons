frappe.ui.form.on('Salary Structure Assignment', {
    refresh: function(frm) {
        check_ot_settings_salary_assignment(frm);
    },
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

function check_ot_settings_salary_assignment(frm) {
    frappe.call({
        method: 'frappe.client.get_single_value',
        args: {
            doctype: 'HR Addons Settings',
            field: 'disable_ot'
        },
        callback: function(r) {
            if (r.message) {
                // Hide OT related fields
                frm.set_df_property('custom_ot_applicable', 'hidden', 1);
                frm.set_df_property('custom_ot_rate', 'hidden', 1);
                frm.set_df_property('custom_ot_amount_calculation', 'hidden', 1);
                frm.set_df_property('custom_standard_multiplier', 'hidden', 1);
            } else {
                frm.set_df_property('custom_ot_applicable', 'hidden', 0);
                frm.set_df_property('custom_ot_rate', 'hidden', 0);
                frm.set_df_property('custom_ot_amount_calculation', 'hidden', 0);
                frm.set_df_property('custom_standard_multiplier', 'hidden', 0);
            }
        }
    });
}

