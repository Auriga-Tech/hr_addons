frappe.ui.form.on('Salary Slip', {
    refresh: function(frm) {
        check_ot_settings_salary_slip(frm);
    }
});

function check_ot_settings_salary_slip(frm) {
    frappe.call({
        method: 'frappe.client.get_single_value',
        args: {
            doctype: 'HR Addons Settings',
            field: 'disable_ot'
        },
        callback: function(r) {
            if (r.message) {
                // Hide OT related fields
                frm.set_df_property('custom_overtimein_hours', 'hidden', 1);
                // Add other OT fields in salary slip if any
            } else {
                frm.set_df_property('custom_overtimein_hours', 'hidden', 0);
            }
        }
    });
}