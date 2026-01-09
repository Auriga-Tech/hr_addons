import frappe
from frappe.utils import flt, time_diff_in_hours

def update_attendance_status_based_on_threshold(attendance):
    """Update attendance status based on working hours thresholds"""
    print("update_attendance_status_based_on_threshold")
    if not attendance.shift:
        return
        
    emp_shift = frappe.get_doc("Shift Type", attendance.shift)
    
    if not emp_shift:
        return
    
    working_hours = flt(attendance.working_hours or 0)
    absent_threshold = flt(emp_shift.get("working_hours_threshold_for_absent") or 0)
    half_day_threshold = flt(emp_shift.get("working_hours_threshold_for_half_day") or 0)
    
    status = None
    
    if working_hours < absent_threshold:
        status = "Absent"
    elif working_hours < half_day_threshold:
        status = "Half Day"
    if status and status != attendance.status:
        attendance.status = status
        frappe.db.set_value("Attendance", attendance.name, "status", status)
        frappe.logger().info(f"Updated attendance {attendance.name} status to {status}")

@frappe.whitelist()
def test_gatepass_configuration():
    """Test gatepass configuration settings"""
    settings = frappe.get_single("Gatepass Setting")
    
    messages = []
    
    # Check if custom fields exist
    custom_fields = [
        "Attendance-custom_actual_working_hours",
        "Attendance-custom_deduction_hours", 
        "Attendance-custom_gp_out_time",
        "Attendance-custom_gp_in_time",
        "Attendance-custom_gatpass_"
    ]
    
    missing_fields = []
    for field in custom_fields:
        if not frappe.db.exists("Custom Field", field):
            missing_fields.append(field)
    
    if missing_fields:
        messages.append(f"Missing custom fields: {', '.join(missing_fields)}")
    else:
        messages.append("✓ All custom fields are present")
    
    # Check settings
    if settings.deduct_from_working_hours:
        messages.append("✓ Working hour deduction is enabled")
    else:
        messages.append("⚠ Working hour deduction is disabled")
    
    if settings.create_auto_checkin_using_shift_if_not_returned:
        messages.append("✓ Auto check-in creation is enabled")
    
    if settings.enable_qr_verification:
        messages.append("✓ QR code verification is enabled")
    
    return "<br>".join(messages)

def round_time_based_on_setting(hours, rounding_method):
    """Round time based on gatepass setting"""
    if rounding_method == "No Rounding":
        return hours
    elif rounding_method == "Round to nearest 15 minutes":
        return round(hours * 4) / 4
    elif rounding_method == "Round to nearest 30 minutes":
        return round(hours * 2) / 2
    elif rounding_method == "Round up":
        import math
        return math.ceil(hours * 4) / 4
    elif rounding_method == "Round down":
        import math
        return math.floor(hours * 4) / 4
    else:
        return hours

def send_gatepass_notification(doc, method=None):
    """Send notification when gatepass is submitted"""
    settings = frappe.get_single("Gatepass Setting")
    
    if not settings.notify_on_gatepass_submit:
        return
    
    # Get employee email and manager
    employee = frappe.get_doc("Employee", doc.employee)
    
    recipients = []
    if employee.company_email:
        recipients.append(employee.company_email)
    
    if employee.reports_to:
        manager = frappe.get_doc("Employee", employee.reports_to)
        if manager.company_email:
            recipients.append(manager.company_email)
    
    if recipients:
        subject = f"Gatepass Submitted - {doc.name}"
        message = f"""
        <p>A new gatepass has been submitted:</p>
        <ul>
            <li>Employee: {doc.employee_name}</li>
            <li>Type: {doc.type}</li>
            <li>Out Time: {doc.out_time}</li>
            <li>Reason: {doc.remark or 'N/A'}</li>
        </ul>
        """
        
        frappe.sendmail(
            recipients=recipients,
            subject=subject,
            message=message
        )
