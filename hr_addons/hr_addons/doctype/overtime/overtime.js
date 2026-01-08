frappe.ui.form.on('Overtime', {
	refresh: function (frm) {
		frm.set_query('primary_department', function() {
            return {
                filters: [
                    ["parent_department", "in", ["All Departments",""]]
                ],
                or_filters: {
                    "old_parent": ["=", "All Departments"]
                }
            };
        });

        if (frm.doc.primary_department) {
            frm.trigger("primary_department");
        }

		// frm.set_df_property("primary_department", "read_only", frm.is_new() ? 0 : 1);
		// frm.set_df_property("primary_sub_department", "read_only", frm.is_new() ? 0 : 1);
		frm.fields_dict['employees'].grid.get_field('employee').get_query = function(doc, cdt, cdn) {
			// child = locals[cdt][cdn];
			console.log("department",frm.doc.department)
						return{	
					filters:[
						['department', '=', frm.doc.primary_department]
					]
				}
			}
		if (frm.doc.docstatus == 0) {
			if (!frm.is_new()) {
				// frm.page.clear_primary_action();
				frm.add_custom_button(__("Get Employees"),
					function () {
						frm.events.get_employee_details(frm);
					}
				).toggleClass('btn-primary', !(frm.doc.employees || []).length);
			}
		}
	},


	primary_department: function(frm) {
        if (frm.doc.primary_department) {
            let previous_value = frm.doc.primary_department;

            frm.set_query('primary_sub_department', function() {
                if (frm.doc.primary_department === "All Departments") {
                    return {};
                } else {
                    return {
                        filters: {
                            parent_department: frm.doc.primary_department
                        }
                    };
                }
            });
            // Clear sub-department only if the department is changed manually
            if (frm.is_dirty() && frm.doc.primary_department !== previous_value) {
                frm.set_value("primary_sub_department", null);
            }
            frm.refresh_field("primary_sub_department");
        }
    },

	get_employee_details: function (frm) {
		return frappe.call({
			doc: frm.doc,
			method: 'fill_employee_details',
		}).then(r => {
			if (r.docs && r.docs[0].employees) {
				frm.employees = r.docs[0].employees;
				frm.dirty();
				frm.save();
				frm.refresh();
			}
		});
	},
	validate: function(frm) {
        if (frm.doc.from_date > frm.doc.to_date) {
            frappe.throw(__("From Date cannot be greater than To Date."));
        }
    },
	apply_to_all:function(frm){
		if (frm.doc.hourly_ot <= 0){
			frappe.throw(__('Overtime hours is less than zero'))
		}
		frappe.confirm('Are you sure you want to apply for all employees?',
		() => {
			// action to perform if Yes is selected
			if (frm.doc.hourly_ot > 0){
				frappe.call({
					doc: frm.doc,
					method: 'set_hourly_ot',
				}).then(r => {
					if (r.docs && r.docs[0].employees) {
						frm.employees = r.docs[0].employees;
						frm.dirty();
						frm.save();
						frm.refresh();
					}
				});
			}
		},  
		() => {
			// action to perform if No is selected
			console.log("No action required");
		})
	},
});