import frappe
from frappe import _
from frappe.utils import get_datetime, now_datetime

@frappe.whitelist(allow_guest=True)
def verify_gatepass(gatepass_id):
    """API endpoint to verify gatepass using QR code"""
    try:
        if not gatepass_id:
            return {"status": "error", "message": "Gatepass ID is required"}
        
        # Check if gatepass exists
        gatepass = frappe.get_value("Gatepass", gatepass_id, 
            ["name", "employee", "employee_name", "type", "out_time", "in_time", "docstatus"], 
            as_dict=True)
        
        if not gatepass:
            return {"status": "error", "message": "Invalid gatepass ID"}
        
        if gatepass.docstatus != 1:
            return {"status": "error", "message": "Gatepass is not submitted"}
        
        # Get current time for verification
        current_time = now_datetime()
        out_time = get_datetime(gatepass.out_time)
        
        # Determine status
        if gatepass.in_time:
            in_time = get_datetime(gatepass.in_time)
            if current_time > in_time:
                status = "Returned"
            else:
                status = "Expected Return"
        else:
            if current_time > out_time:
                status = "Out - No Return Time Set"
            else:
                status = "Scheduled"
        
        return {
            "status": "success",
            "data": {
                "gatepass_id": gatepass.name,
                "employee": gatepass.employee_name,
                "type": gatepass.type,
                "out_time": gatepass.out_time,
                "in_time": gatepass.in_time,
                "current_status": status,
                "verified_at": current_time
            }
        }
        
    except Exception as e:
        frappe.log_error(f"Gatepass verification failed: {e}", "Gatepass API Error")
        return {"status": "error", "message": "Verification failed"}

@frappe.whitelist()
def get_employee_gatepasses(employee, from_date=None, to_date=None):
    """Get gatepasses for an employee within date range"""
    filters = {"employee": employee, "docstatus": 1}
    
    if from_date:
        filters["out_time"] = [">=", from_date]
    if to_date:
        if "out_time" in filters:
            filters["out_time"] = ["between", [from_date, to_date]]
        else:
            filters["out_time"] = ["<=", to_date]
    
    gatepasses = frappe.get_all("Gatepass",
        filters=filters,
        fields=["name", "type", "out_time", "in_time", "remark", "attendance_marked"],
        order_by="out_time desc"
    )
    
    return gatepasses

@frappe.whitelist()
def mark_gatepass_return(gatepass_id, return_time=None):
    """Mark gatepass return time"""
    if not return_time:
        return_time = now_datetime()
    
    gatepass = frappe.get_doc("Gatepass", gatepass_id)
    
    if gatepass.docstatus != 1:
        frappe.throw("Gatepass must be submitted first")
    
    if gatepass.in_time:
        frappe.throw("Return time is already marked")
    
    gatepass.db_set("in_time", return_time)
    
    return {"status": "success", "message": "Return time marked successfully"}

@frappe.whitelist(allow_guest=True)
def mark_gatepass_return_with_validation(gatepass_id, employee, return_time):
    """Mark gatepass return time with employee validation"""
    try:
        if not gatepass_id or not employee or not return_time:
            return {"status": "error", "message": "Gatepass ID, Employee, and Return Time are required"}
        
        # Get gatepass (ignore permissions for guest access)
        frappe.flags.ignore_permissions = True
        gatepass = frappe.get_doc("Gatepass", gatepass_id)
        frappe.flags.ignore_permissions = False
        
        # Allow both draft and submitted gatepasses
        # Removed docstatus check
        
        # Validate employee
        if gatepass.employee != employee:
            return {"status": "error", "message": "Employee ID does not match the gatepass"}
        
        # Check if already returned
        if gatepass.in_time:
            return {"status": "error", "message": "Return time is already marked"}
        
        # Mark return time
        gatepass.db_set("in_time", return_time)
        frappe.db.commit()
        
        return {
            "status": "success",
            "message": f"Return marked successfully for {gatepass.employee_name}",
            "data": {
                "gatepass_id": gatepass.name,
                "employee": gatepass.employee_name,
                "return_time": return_time
            }
        }
        
    except Exception as e:
        frappe.log_error(f"Mark return failed: {e}", "Gatepass API Error")
        return {"status": "error", "message": str(e)}

@frappe.whitelist()
def get_gatepass_statistics(employee=None, from_date=None, to_date=None):
    """Get gatepass statistics"""
    filters = {"docstatus": 1}
    
    if employee:
        filters["employee"] = employee
    if from_date:
        filters["out_time"] = [">=", from_date]
    if to_date:
        if "out_time" in filters:
            filters["out_time"] = ["between", [from_date, to_date]]
        else:
            filters["out_time"] = ["<=", to_date]
    
    # Get basic counts
    total_gatepasses = frappe.db.count("Gatepass", filters)
    
    personal_filters = filters.copy()
    personal_filters["type"] = "Personal"
    personal_count = frappe.db.count("Gatepass", personal_filters)
    
    official_filters = filters.copy()
    official_filters["type"] = "Official"
    official_count = frappe.db.count("Gatepass", official_filters)
    
    # Get pending returns
    pending_filters = filters.copy()
    pending_filters["in_time"] = ["is", "not set"]
    pending_returns = frappe.db.count("Gatepass", pending_filters)
    
    return {
        "total_gatepasses": total_gatepasses,
        "personal_gatepasses": personal_count,
        "official_gatepasses": official_count,
        "pending_returns": pending_returns
    }
