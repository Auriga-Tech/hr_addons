import frappe
import datetime
from frappe.utils import time_diff_in_hours, get_datetime, flt
from hr_addons.utils.gatepass_utils import update_attendance_status_based_on_threshold, round_time_based_on_setting

@frappe.whitelist()
def apply_gatepass_deduction(doc, method):
    """Apply gatepass deduction to attendance"""
    settings = frappe.get_single("Gatepass Setting")
    
    if not settings.deduct_from_working_hours:
        return
    
    attendance_date = doc.attendance_date
    
    # Define full-day range
    attendance_start = datetime.datetime.strptime(str(attendance_date) + " 00:00:00", "%Y-%m-%d %H:%M:%S")
    attendance_end = datetime.datetime.strptime(str(attendance_date) + " 23:59:59", "%Y-%m-%d %H:%M:%S")
    
    # Get gatepasses for this employee and date that haven't been processed
    gatepasses = frappe.get_all("Gatepass",
        filters={
            "employee": doc.employee,
            "docstatus": 1,
            "type": "Personal",  # Only personal gatepasses affect attendance
            "out_time": ["between", [attendance_start, attendance_end]],
            "attendance_marked": ["is", "not set"]
        },
        fields=["name", "in_time", "out_time"]
    )
    
    total_deduction = 0
    used_gatepasses = []
    earliest_out_time = None
    latest_in_time = None
    
    for gp in gatepasses:
        if gp.in_time and gp.out_time:
            try:
                in_time = get_datetime(gp.in_time)
                out_time = get_datetime(gp.out_time)
                
                # For personal gatepasses, out_time should be before in_time
                if out_time >= in_time:
                    continue
                    
                hours = time_diff_in_hours(in_time, out_time)
                
                # Apply minimum deduction threshold
                min_deduction_hours = flt(settings.minimum_deduction_minutes or 0) / 60
                if hours < min_deduction_hours:
                    hours = min_deduction_hours
                
                # Apply rounding if configured
                hours = round_time_based_on_setting(hours, settings.rounding_method)
                
                total_deduction += hours
                used_gatepasses.append(gp.name)
                
                # Track earliest out_time and latest in_time
                if not earliest_out_time or out_time < earliest_out_time:
                    earliest_out_time = out_time
                if not latest_in_time or in_time > latest_in_time:
                    latest_in_time = in_time
                
                # Mark gatepass as used
                frappe.db.set_value("Gatepass", gp.name, "attendance_marked", doc.name)
                
            except Exception as e:
                frappe.log_error(f"Gatepass Time Parsing Failed for {gp.name}: {e}", "Gatepass Processing Error")
    
    # Update Attendance fields if deduction is applicable
    if total_deduction > 0:
        # Store original working hours if not already stored
        if not doc.custom_actual_working_hours:
            doc.custom_actual_working_hours = doc.working_hours or 0
        
        # Deduct hours from working hours
        doc.working_hours = max(doc.custom_actual_working_hours - total_deduction, 0)
        doc.custom_deduction_hours = total_deduction
        doc.custom_gatpass_ = ", ".join(used_gatepasses)
        
        if earliest_out_time:
            doc.custom_gp_out_time = earliest_out_time
        if latest_in_time:
            doc.custom_gp_in_time = latest_in_time
    
    # Update attendance status based on working hours threshold
    if settings.update_status_after_attendance_submitted and doc:
        update_attendance_status_based_on_threshold(doc)
