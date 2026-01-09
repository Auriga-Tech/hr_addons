frappe.ui.form.on('Employee', {
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
                // If OT is disabled globally
               
                frm.set_df_property('custom_ot_applicable', 'read_only', 1);
                frm.set_value('custom_ot_applicable', 'No');
            } else {
                frm.set_df_property('custom_ot_applicable', 'hidden', 0);
                frm.set_df_property('custom_ot_applicable', 'read_only', 0);
            }
        }
    });
}