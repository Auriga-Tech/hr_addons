import frappe
from frappe.utils import get_datetime, now_datetime

# Allow guest access - no login required
no_cache = 1

def get_context(context):
    """Get context for the gatepass verification page"""
    # Initialize context variables
    context.error = None
    context.gatepass = None
    context.already_returned = False
    context.return_time = None
    context.current_time = now_datetime()
    
    gatepass_id = frappe.form_dict.get('gatepass_id')
    
    if not gatepass_id:
        context.error = "Gatepass ID is required"
        return context
    
    try:
        # Get gatepass details (ignore permissions for guest access)
        # Use frappe.get_doc with flags instead of get_value
        frappe.flags.ignore_permissions = True
        
        gatepass_doc = frappe.get_doc("Gatepass", gatepass_id)
        
        if not gatepass_doc:
            context.error = "Invalid Gatepass ID"
            return context
        
        # Allow both draft (0) and submitted (1) gatepasses
        # Removed docstatus check
        
        # Convert to dict for template
        context.gatepass = {
            "name": gatepass_doc.name,
            "employee": gatepass_doc.employee,
            "employee_name": gatepass_doc.employee_name,
            "department": gatepass_doc.department,
            "type": gatepass_doc.type,
            "out_time": gatepass_doc.out_time,
            "in_time": gatepass_doc.in_time,
            "docstatus": gatepass_doc.docstatus
        }
        
        # Check if already returned
        if gatepass_doc.in_time:
            context.already_returned = True
            context.return_time = gatepass_doc.in_time
        
    except Exception as e:
        frappe.log_error(f"Error loading gatepass: {e}", "Gatepass Verification Error")
        context.error = f"Failed to load gatepass details: {str(e)}"
    finally:
        # Reset the flag
        frappe.flags.ignore_permissions = False
    
    return context
