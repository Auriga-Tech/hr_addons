import frappe
from hrms.hr.doctype.attendance.attendance import Attendance as BaseAttendance

class Attendance(BaseAttendance):
    def before_cancel(self):
        """Handle attendance cancellation - unlink related gatepasses"""
        # super().before_cancel()
        self._unlink_gatepasses()
        
    def _unlink_gatepasses(self):
        """Unlink Gatepass records linked to this attendance"""
        gatepasses = frappe.get_all("Gatepass",
            filters={
                "employee": self.employee,
                "attendance_marked": self.name
            },
            fields=["name"]
        )
        
        for gp in gatepasses:
            frappe.db.set_value("Gatepass", gp.name, {
                "attendance_marked": None,
                "checkin_marked": None
            })
            
        if gatepasses:
            frappe.msgprint(f"Unlinked {len(gatepasses)} gatepass record(s) from this attendance")
