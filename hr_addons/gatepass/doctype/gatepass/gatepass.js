frappe.ui.form.on("Gatepass", {
    refresh: function (frm) {
        // Show QR buttons only for saved gatepasses with valid ID
        // Must be saved (has a proper ID) and is draft
        if (frm.doc.name &&
            !frm.doc.name.startsWith('new-') &&
            frm.doc.name.length > 10 &&
            frm.doc.docstatus === 0) {

            // Check Gatepass Setting to see if QR verification is enabled
            frappe.db.get_single_value('Gatepass Setting', 'enable_qr_verification')
                .then(enable_qr => {
                    if (enable_qr) {
                        // Show Generate QR button only if:
                        // 1. QR code is not generated yet
                        // 2. in_time does NOT exist (employee hasn't returned)
                        if (!frm.doc.qr && !frm.doc.in_time) {
                            frm.add_custom_button(__('Generate QR Code'), function () {
                                frappe.call({
                                    method: "hr_addons.gatepass.doctype.gatepass.gatepass.generate_qr_from_button",
                                    args: {
                                        gatepass_id: frm.doc.name
                                    },
                                    callback: function (r) {
                                        if (r.message) {
                                            frappe.show_alert({
                                                message: __("QR Code generated successfully"),
                                                indicator: 'green'
                                            });
                                            // Reload after a short delay to avoid conflict
                                            setTimeout(() => frm.reload_doc(), 500);
                                        }
                                    }
                                });
                            }).addClass("btn-primary");
                        }

                        // Show Print QR Code button if QR exists
                        if (frm.doc.qr) {
                            frm.add_custom_button(__('Print QR Code'), function () {
                                frm.trigger('print_qr_code');
                            });
                        }
                    }
                });
        }

        // Display QR Code
        if (frm.doc.qr) {
            frm.fields_dict["qr_code"].$wrapper.html(
                `<div style="text-align: center; padding: 10px;">
                    <img src="${frm.doc.qr}" style="max-width:200px; border:1px solid #ddd; padding:5px;"/>
                    <p><small>Scan to verify gatepass</small></p>
                </div>`
            );
        } else {
            frm.fields_dict["qr_code"].$wrapper.html(
                "<p style='text-align: center; color: #888;'>No QR code generated</p>"
            );
        }
    },

    // Whenever QR field changes, refresh the preview
    qr: function (frm) {
        if (frm.doc.qr) {
            frm.fields_dict["qr_code"].$wrapper.html(
                `<div style="text-align: center; padding: 10px;">
                    <img src="${frm.doc.qr}" style="max-width:200px; border:1px solid #ddd; padding:5px;"/>
                    <p><small>Scan to verify gatepass</small></p>
                </div>`
            );
        } else {
            frm.fields_dict["qr_code"].$wrapper.html(
                "<p style='text-align: center; color: #888;'>No QR code generated</p>"
            );
        }
    },

    print_qr_code: function (frm) {
        let printWindow = window.open('', '_blank');
        printWindow.document.write(`
            <html>
                <head>
                    <title>Gatepass QR Code - ${frm.doc.name}</title>
                    <style>
                        body { font-family: Arial, sans-serif; text-align: center; margin: 50px; }
                        .qr-container { border: 1px solid #ddd; padding: 20px; display: inline-block; }
                        img { max-width: 300px; }
                        h3 { margin-bottom: 20px; }
                        .details { margin-top: 20px; text-align: left; }
                        @media print { .no-print { display: none; } }
                    </style>
                </head>
                <body>
                    <div class="qr-container">
                        <h3>Gatepass QR Code</h3>
                        <img src="${frm.doc.qr}" />
                        <div class="details">
                            <p><strong>Gatepass ID:</strong> ${frm.doc.name}</p>
                            <p><strong>Employee:</strong> ${frm.doc.employee_name}</p>
                            <p><strong>Type:</strong> ${frm.doc.type}</p>
                            <p><strong>Out Time:</strong> ${frappe.datetime.str_to_user(frm.doc.out_time)}</p>
                            ${frm.doc.in_time ? '<p><strong>In Time:</strong> ' + frappe.datetime.str_to_user(frm.doc.in_time) + '</p>' : ''}
                        </div>
                    </div>
                    <script>
                        window.onload = function() {
                            window.print();
                            window.onafterprint = function() {
                                window.close();
                            };
                        };
                    </script>
                </body>
            </html>
        `);
        printWindow.document.close();
    },

    type: function (frm) {
        // Add validation or business logic based on type
        if (frm.doc.type === "Personal") {
            frm.set_df_property('remark', 'reqd', 1);
        } else {
            frm.set_df_property('remark', 'reqd', 0);
        }
    },

    employee: function (frm) {
        // Clear dependent fields when employee changes
        if (frm.doc.employee) {
            frm.set_value('employee_name', '');
            frm.set_value('department', '');
        }
    }
});

// List View customizations
frappe.listview_settings['Gatepass'] = {
    add_fields: ["employee_name", "type", "out_time", "in_time"],
    get_indicator: function (doc) {
        if (doc.docstatus === 0) {
            return [__("Draft"), "red", "docstatus,=,0"];
        } else if (doc.docstatus === 1) {
            if (doc.in_time) {
                return [__("Returned"), "green", "docstatus,=,1|in_time,!=,"];
            } else {
                return [__("Out"), "orange", "docstatus,=,1|in_time,=,"];
            }
        } else if (doc.docstatus === 2) {
            return [__("Cancelled"), "red", "docstatus,=,2"];
        }
    }
};
