frappe.ui.form.on('Shift Type', {
    refresh: function(frm) {
        check_ot_settings_shift_type(frm);
    }
});

function check_ot_settings_shift_type(frm) {
    frappe.call({
        method: 'frappe.client.get_single_value',
        args: {
            doctype: 'HR Addons Settings',
            field: 'disable_ot'
        },
        callback: function(r) {
            if (r.message) {
                // Hide OT related fields
                frm.set_df_property('custom_allow_overtime', 'hidden', 1);
                frm.set_df_property('custom_overtime_type', 'hidden', 1);
                frm.set_df_property('custom_maximum_overtime_hours_allowed', 'hidden', 1);
                frm.set_df_property('custom_section_break_dv9zx', 'hidden', 1);
            } else {
                frm.set_df_property('custom_allow_overtime', 'hidden', 0);
                frm.set_df_property('custom_overtime_type', 'hidden', 0);
                frm.set_df_property('custom_maximum_overtime_hours_allowed', 'hidden', 0);
                frm.set_df_property('custom_section_break_dv9zx', 'hidden', 0);
            }
        }
    });
}