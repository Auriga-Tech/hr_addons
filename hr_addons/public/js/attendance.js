frappe.ui.form.on('Attendance', {
    refresh: function(frm) {
        check_ot_settings_attendance(frm);
    }
});

function check_ot_settings_attendance(frm) {
    frappe.call({
        method: 'frappe.client.get_single_value',
        args: {
            doctype: 'HR Addons Settings',
            field: 'disable_ot'
        },
        callback: function(r) {
            if (r.message) {
                // Hide entire overtime section and all OT related fields
                frm.set_df_property('custom_overtime_checkin', 'hidden', 1);
                frm.set_df_property('custom_overtimemarked_in_system', 'hidden', 1);
                frm.set_df_property('custom_effective_overtime_duration', 'hidden', 1);
                frm.set_df_property('custom_standard_working_hours', 'hidden', 1);
            } else {
                frm.set_df_property('custom_overtime_checkin', 'hidden', 0);
                frm.set_df_property('custom_overtimemarked_in_system', 'hidden', 0);
                frm.set_df_property('custom_effective_overtime_duration', 'hidden', 0);
                frm.set_df_property('custom_standard_working_hours', 'hidden', 0);
                frm.set_df_property('overtime_section', 'hidden', 0);
            }
        }
    });
}