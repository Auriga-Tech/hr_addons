frappe.ui.form.on('Employee Checkin', {
    refresh: function(frm) {
        check_ot_settings(frm);
    }
});

function check_ot_settings(frm) {
    frappe.call({
        method: 'frappe.client.get_single_value',
        args: {
            doctype: 'HR Addons Settings',
            field: 'disable_ot'
        },
            callback: function(r) {
                if (r.message) {
                    frm.set_df_property('custom_overtime_type', 'hidden', 1);

                }
                else{
                    frm.set_df_property('custom_overtime_type', 'hidden', 0);
                }
            }
        });
    }
