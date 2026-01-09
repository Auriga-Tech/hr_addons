import frappe
import qrcode
import base64
from io import BytesIO
from datetime import datetime
from frappe.model.document import Document
from frappe.utils import get_datetime, time_diff_in_hours
from hr_addons.utils.gatepass_utils import update_attendance_status_based_on_threshold, round_time_based_on_setting
from frappe.model.naming import make_autoname


class Gatepass(Document):
    def on_submit(self):
        settings = frappe.get_single("Gatepass Setting")

        # Track if in_time was auto-set by create_checkin
        in_time_was_auto_set = False
        
        # Auto checkin if required
        if not self.in_time:
            in_time_was_auto_set = self.create_checkin(settings)

        # Deduct hours for personal gatepasses only
        # Skip if in_time was auto-set (checkin will handle the deduction)
        if self.type == "Personal" and not in_time_was_auto_set:
            self.update_attendance(settings)

    def create_checkin(self, settings):
        """Create an Employee Checkin automatically when Gatepass is submitted.
        Returns True if in_time was auto-set, False otherwise."""
        if not settings.create_auto_checkin_using_shift_if_not_returned:
            return False

        out_time = get_datetime(self.out_time)

        # Get checkins for that date
        checkin_data = frappe.get_all(
            "Employee Checkin",
            filters=[
                ["employee", "=", self.employee],
                ["time", ">=", f"{out_time.date()} 00:00:00"],
                ["time", "<=", f"{out_time.date()} 23:59:59"],
            ],
            fields=["name", "shift"],
        )

        if checkin_data:
            shift = checkin_data[0].get("shift")
            emp_shift = frappe.get_doc("Shift Type", shift)
            shift_end_time = get_datetime(f"{out_time.date()} {emp_shift.end_time}")

            # When employee doesn't return, create checkin at shift end time
            # This marks them as having left at the end of shift
            checkin_time = shift_end_time

            # Update Gatepass in_time to shift end time
            frappe.db.set_value("Gatepass", self.name, "in_time", shift_end_time)

            checkin_doc = frappe.get_doc({
                "doctype": "Employee Checkin",
                "employee": self.employee,
                "time": checkin_time,
            })
            checkin_doc.insert(ignore_permissions=True)

            frappe.db.set_value("Gatepass", self.name, "checkin_marked", checkin_doc.name)
            frappe.db.commit()
            
            # Return True to indicate in_time was auto-set
            return True
        
        return False

    def update_attendance(self, settings):
        """Deduct gatepass hours from Attendance."""
        if not settings.deduct_from_working_hours:
            return
        if self.attendance_marked:
            return
        if not self.out_time:
            return

        try:
            in_time = get_datetime(self.in_time)
            out_time = get_datetime(self.out_time)

            # Ensure valid times
            if out_time >= in_time:
                return

            deduction_hours = time_diff_in_hours(in_time, out_time)

            attendance = frappe.get_value(
                "Attendance",
                {
                    "employee": self.employee,
                    "attendance_date": out_time.date(),
                    "docstatus": 1,
                },
                ["name", "working_hours", "shift", "custom_actual_working_hours"],
                as_dict=True,
            )

            if attendance:
                # Preserve original working hours
                if not attendance.custom_actual_working_hours:
                    frappe.db.set_value(
                        "Attendance",
                        attendance.name,
                        "custom_actual_working_hours",
                        attendance.working_hours,
                    )

                # Deduct hours
                frappe.db.set_value(
                    "Attendance",
                    attendance.name,
                    "working_hours",
                    max((attendance.working_hours or 0) - deduction_hours, 0),
                )
                frappe.db.set_value("Gatepass", self.name, "attendance_marked", attendance.name)

                # Update aggregate custom fields
                update_gatepass_fields_in_attendance(self.employee, out_time.date(), attendance.name)

                # Optionally recheck status
                if settings.update_status_after_attendance_submitted:
                    attendance_doc = frappe.get_doc("Attendance", attendance.name)
                    update_attendance_status_based_on_threshold(attendance_doc)

        except Exception as e:
            frappe.log_error(f"Gatepass deduction failed: {e}", "Gatepass Error")

    def on_cancel(self):
        """Reverse attendance deductions if Gatepass is cancelled."""
        settings = frappe.get_single("Gatepass Setting")
        if not settings.deduct_from_working_hours:
            return
        if not self.attendance_marked:
            return
        if not (self.in_time and self.out_time):
            return

        try:
            in_time = get_datetime(self.in_time)
            out_time = get_datetime(self.out_time)
            if out_time >= in_time:
                return

            deduction_hours = time_diff_in_hours(in_time, out_time)

            attendance = frappe.get_value(
                "Attendance",
                {
                    "employee": self.employee,
                    "attendance_date": out_time.date(),
                    "docstatus": 1,
                },
                ["name", "working_hours"],
                as_dict=True,
            )

            if attendance:
                frappe.db.set_value(
                    "Attendance",
                    attendance.name,
                    "working_hours",
                    max((attendance.working_hours or 0) + deduction_hours, 0),
                )
                frappe.db.set_value("Gatepass", self.name, "attendance_marked", "")

        except Exception as e:
            frappe.log_error(f"Gatepass cancel failed: {e}", "Gatepass Cancel Error")

    def autoname(self):
        """Auto-name Gatepass by type, month, year."""
        current_date = datetime.now()
        month = current_date.strftime("%m")
        year = current_date.strftime("%Y")

        if self.type == "Personal":
            series = f"GPP-{month}-{year}-.######"
        elif self.type == "Official":
            series = f"GPO-{month}-{year}-.######"
        else:
            frappe.throw("Invalid Gatepass Type")

        self.name = make_autoname(series)

    def generate_qr(self):
        """Generate QR code for gatepass verification."""
        if not self.employee:
            frappe.throw("Employee is missing, cannot generate QR.")
        if not self.out_time:
            frappe.throw("Out Time is missing, cannot generate QR.")
        if not self.type:
            frappe.throw("Gatepass Type is missing, cannot generate QR.")

        # Point to the verification web page instead of API
        url = f"{frappe.utils.get_url()}/gatepass/verify?gatepass_id={self.name}"

        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        buffer = BytesIO()
        img.save(buffer, format="PNG")
        qr_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
        qr_code_str = f"data:image/png;base64,{qr_base64}"

        self.db_set("qr", qr_code_str)
        return qr_code_str


def update_gatepass_fields_in_attendance(employee, attendance_date, attendance_name):
    """Recalculate custom fields on Attendance based on all gatepasses of the day."""
    gatepasses = frappe.get_all(
        "Gatepass",
        filters={
            "employee": employee,
            "docstatus": 1,
            "out_time": ["between", [f"{attendance_date} 00:00:00", f"{attendance_date} 23:59:59"]],
            "attendance_marked": attendance_name,
        },
        fields=["name", "in_time", "out_time"],
    )

    total_hours = 0
    earliest_out = None
    latest_in = None
    names = []

    for gp in gatepasses:
        if gp.in_time and gp.out_time:
            try:
                in_time = get_datetime(gp.in_time)
                out_time = get_datetime(gp.out_time)

                if out_time > in_time:
                    continue

                names.append(gp.name)
                total_hours += time_diff_in_hours(in_time, out_time)

                if not earliest_out or out_time < earliest_out:
                    earliest_out = out_time
                if not latest_in or in_time > latest_in:
                    latest_in = in_time

            except Exception as e:
                frappe.log_error(f"Error parsing gatepass {gp.name}: {e}", "Gatepass Time Error")

    frappe.db.set_value(
        "Attendance",
        attendance_name,
        {
            "custom_gp_out_time": earliest_out,
            "custom_gp_in_time": latest_in,
            "custom_deduction_hours": total_hours,
            "custom_gatpass_": ", ".join(names),
        },
    )


@frappe.whitelist()
def generate_qr_from_button(gatepass_id):
    doc = frappe.get_doc("Gatepass", gatepass_id)
    return doc.generate_qr()
