import frappe
from frappe.utils import cint, create_batch
from itertools import groupby
from hrms.hr.doctype.shift_type.shift_type import ShiftType as BaseShiftType
from hrms.hr.doctype.employee_checkin.employee_checkin import mark_attendance_and_link_log

EMPLOYEE_CHUNK_SIZE = 50

class ShiftType(BaseShiftType):
    @frappe.whitelist()
    def process_auto_attendance(self):
        self.update_gatepass_status()
        if (
            not cint(self.enable_auto_attendance)
            or not self.process_attendance_after
            or not self.last_sync_of_checkin
        ):
            return

        logs = self.get_employee_checkins()

        group_key = lambda x: (x["employee"], x["shift_start"])  # noqa
        for key, group in groupby(sorted(logs, key=group_key), key=group_key):
            single_shift_logs = list(group)
            attendance_date = key[1].date()
            employee = key[0]

            if not self.should_mark_attendance(employee, attendance_date):
                continue

            (
                attendance_status,
                working_hours,
                late_entry,
                early_exit,
                in_time,
                out_time,
            ) = self.get_attendance(single_shift_logs)

            mark_attendance_and_link_log(
                single_shift_logs,
                attendance_status,
                attendance_date,
                working_hours,
                late_entry,
                early_exit,
                in_time,
                out_time,
                self.name,
            )

        # commit after processing checkin logs to avoid losing progress
        frappe.db.commit()  # nosemgrep

        assigned_employees = self.get_assigned_employees(self.process_attendance_after, True)

        # mark absent in batches & commit to avoid losing progress since this tries to process remaining attendance
        # right from "Process Attendance After" to "Last Sync of Checkin"
        for batch in create_batch(assigned_employees, EMPLOYEE_CHUNK_SIZE):
            for employee in batch:
                self.mark_absent_for_dates_with_no_attendance(employee)

            frappe.db.commit()  # nosemgrep
            
    def update_gatepass_status(self):
        """Update and submit all Gatepass records with docstatus 0."""
        gatepass_records = frappe.get_all(
            "Gatepass",
            filters={"docstatus": 0},
            fields=["name"]
        )

        for gatepass in gatepass_records:
            doc = frappe.get_doc("Gatepass", gatepass["name"])
            doc.docstatus = 1
            doc.submit()
            frappe.db.commit()
