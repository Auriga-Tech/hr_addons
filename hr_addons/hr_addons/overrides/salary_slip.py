import frappe
from hrms.payroll.doctype.salary_slip.salary_slip import SalarySlip
from frappe.utils import add_days, flt, getdate, cint, date_diff
from frappe import _
    

class CustomSalarySlip(SalarySlip):
	print("**************************************not original")
	def get_working_days_details(self, lwp=None, for_preview=0):
		payroll_settings = frappe.get_cached_value(
			"Payroll Settings",
			None,
			(
				"payroll_based_on",
				"include_holidays_in_total_working_days",
				"consider_marked_attendance_on_holidays",
				"daily_wages_fraction_for_half_day",
				"consider_unmarked_attendance_as",
			),
			as_dict=1,
		)

		consider_marked_attendance_on_holidays = (
			payroll_settings.include_holidays_in_total_working_days
			and payroll_settings.consider_marked_attendance_on_holidays
		)

		daily_wages_fraction_for_half_day = flt(payroll_settings.daily_wages_fraction_for_half_day) or 0.5

		working_days = date_diff(self.end_date, self.start_date) + 1
		if for_preview:
			self.total_working_days = working_days
			self.payment_days = working_days
			return

		holidays = self.get_holidays_for_employee(self.start_date, self.end_date)
		working_days_list = [add_days(getdate(self.start_date), days=day) for day in range(0, working_days)]

		if not cint(payroll_settings.include_holidays_in_total_working_days):
			working_days_list = [i for i in working_days_list if i not in holidays]

			working_days -= len(holidays)
			if working_days < 0:
				frappe.throw(_("There are more holidays than working days this month."))

		if not payroll_settings.payroll_based_on:
			frappe.throw(_("Please set Payroll based on in Payroll settings"))

		if payroll_settings.payroll_based_on == "Attendance":
			actual_lwp, absent = self.calculate_lwp_ppl_and_absent_days_based_on_attendance(
				holidays, daily_wages_fraction_for_half_day, consider_marked_attendance_on_holidays
			)
			self.absent_days = absent
		else:
			actual_lwp = self.calculate_lwp_or_ppl_based_on_leave_application(
				holidays, working_days_list, daily_wages_fraction_for_half_day
			)

		if not lwp:
			lwp = actual_lwp
		elif lwp != actual_lwp:
			frappe.msgprint(
				_("Leave Without Pay does not match with approved {} records").format(
					payroll_settings.payroll_based_on
				)
			)

		self.leave_without_pay = lwp
		self.total_working_days = working_days

		payment_days = self.get_payment_days(payroll_settings.include_holidays_in_total_working_days)

		if flt(payment_days) > flt(lwp):
			self.payment_days = flt(payment_days) - flt(lwp)

			if payroll_settings.payroll_based_on == "Attendance":
				self.payment_days -= flt(absent)

			consider_unmarked_attendance_as = payroll_settings.consider_unmarked_attendance_as or "Present"

			if payroll_settings.payroll_based_on == "Attendance":
				if consider_unmarked_attendance_as == "Absent":
					unmarked_days = self.get_unmarked_days(
						payroll_settings.include_holidays_in_total_working_days, holidays
					)
					self.absent_days += unmarked_days  # will be treated as absent
					self.payment_days -= unmarked_days
				half_absent_days = self.get_half_absent_days(
					consider_marked_attendance_on_holidays,
					holidays,
				)
				self.absent_days += half_absent_days * daily_wages_fraction_for_half_day
				self.payment_days -= half_absent_days * daily_wages_fraction_for_half_day
		else:
			self.payment_days = 0
			"""Customized changes For overtime Calculation"""
		try:
				print("start_date",self.start_date)
				print("end_date",self.end_date)
				self.custom_overtimein_hours = frappe.get_value(
                    "Attendance",
                    {
                        "employee": self.employee,
                        "attendance_date": ["between", [self.start_date, self.end_date]],
                        "docstatus": 1  # Consider only submitted records
                    },
                    "sum(custom_actual_overtime_duration)"
                ) or 0  # If no records found, return 0
				print("self.custom_overtimein_hours",self.custom_overtimein_hours)
		except Exception as e:
		            frappe.log_error(f"Error in set_overtime_hours: {str(e)}", "Update Error in Overtime")
            # --- NEW LOGIC TO ADD CUSTOM PART RATE AMOUNT ---