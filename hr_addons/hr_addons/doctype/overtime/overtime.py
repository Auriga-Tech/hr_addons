# Copyright (c) 2022, indictranstech and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import (
	DATE_FORMAT,
	add_days,
	add_to_date,
	cint,
	comma_and,
	date_diff,
	flt,
	get_link_to_form,
	getdate,
)
import re
from datetime import date, timedelta



class Overtime(Document):
	def before_validate(self):
		print("before validate",self.employees)
		for otd in self.employees:
			otd.from_date = self.from_date
			otd.to_date = self.to_date
			print("before validate",otd,otd.from_date,otd.to_date) 

	def validate(self):
		self.check_employee_shift_overtime()
		if self.employees:
			temp_emp = [_doc.employee for _doc in self.employees]
			print("temp_emp",temp_emp)
			emp_list = tuple(temp_emp)
			print(emp_list)
			# emp_list_condition = "" if len(emp_list)==0 else f"and otd.employee IN {emp_list}"

			if len(emp_list)==0:
				emp_list_condition = ""
			else:
				if len(emp_list)==1:
					emp_list_condition = f"and otd.employee = '{emp_list[0]}'"
				else:
					emp_list_condition = f"and otd.employee IN {emp_list}"



			from_date = getdate(self.from_date)
			to_date = getdate(self.to_date)
			print(from_date,to_date)
			delta = timedelta(days=1)

			while from_date <= to_date:
				ot_details = frappe.db.sql(f"""
					select otd.employee from `tabOvertime Details` as otd JOIN `tabOvertime` as ot on ot.name = otd.parent where ot.docstatus != 2 and otd.from_date<='{from_date}' and otd.to_date >= '{from_date}' and otd.parent <> '{self.name}' {emp_list_condition}
					""")
				print("ot_deatils",ot_details)
				if len(ot_details)>0:
					frappe.throw(_('Overtime already exists for employees {} on {}'.format(frappe.bold(comma_and(ot_details)), from_date)))
				from_date += delta
		self.check_ot_eligibility() 
	
	# check if its hourly overtime does not exceed its overtime type marked overtime 
	def check_employee_shift_overtime(self):

		for emp_row in self.employees:
			employee = emp_row.employee
			hourly_ot = flt(emp_row.hourly_ot)

			# Get the employee’s shift type
	def check_employee_shift_overtime(self):
		for emp_row in self.employees:
			employee = emp_row.employee
			employee_name=emp_row.employee_name
			hourly_ot = flt(emp_row.hourly_ot)

			from_date = getdate(self.from_date)
			to_date = getdate(self.to_date)
			print("emp_row",emp_row.employee)
			# fetch all overlapping assigned shifts for that employee
			assigned_shifts = frappe.db.get_all(
				"Shift Assignment",
				filters={
					"employee": employee,
					"docstatus": 1,
					"start_date": ("<=", to_date),
					"end_date": (">=", from_date),
				},
				fields=["shift_type", "start_date", "end_date"],
				order_by="start_date asc"
			)
			print("Assigned Shifts",assigned_shifts,hourly_ot)
			checked_periods = []  # store handled date ranges (for overlap removal)

			# Step 1: check all assigned shifts
			for shift in assigned_shifts:
				max_ot = frappe.db.get_value("Shift Type", shift.shift_type, "custom_maximum_overtime_hours_allowed")
				print("max_ot",shift,max_ot)
				if max_ot and hourly_ot > flt(max_ot):
					frappe.throw(_(
						f"Hourly OT ({hourly_ot} hrs) for Employee {frappe.bold(employee)} "
						f"exceeds maximum allowed ({max_ot} hrs) in assigned Shift Type {shift.shift_type} "
						f"from {shift.start_date} to {shift.end_date}."
					))

				# record the handled range
				checked_periods.append((getdate(shift.start_date), getdate(shift.end_date)))

			# Step 2: check if any remaining period (not covered by assignments)
			if not assigned_shifts:
				remaining_periods = [(from_date, to_date)]
			else:
				remaining_periods = []
				current_start = from_date

				for s_start, s_end in sorted(checked_periods):
					# if OT starts before shift start → that part is default shift
					if current_start < s_start:
						remaining_periods.append((current_start, min(s_start - timedelta(days=1), to_date)))
					# move start forward if overlap exists
					if s_end >= current_start:
						current_start = s_end + timedelta(days=1)
					if current_start > to_date:
						break

				# after last assignment, if still time left till OT end
				if current_start <= to_date:
					remaining_periods.append((current_start, to_date))

			# Step 3: check remaining periods against default shift
			if remaining_periods:
				default_shift = frappe.db.get_value("Employee", employee, "default_shift")
				if not default_shift:
					frappe.throw(_(f"Employee {employee} has no default shift for remaining OT period."))

				max_ot = frappe.db.get_value("Shift Type", default_shift, "custom_maximum_overtime_hours_allowed")
				if max_ot and hourly_ot > flt(max_ot):
					for r_start, r_end in remaining_periods:
						frappe.throw(_(
							f"Hourly OT ({hourly_ot} hrs) for Employee {frappe.bold(employee)} exceeds "
							f"maximum allowed ({max_ot} hrs) in Default Shift Type ({default_shift}) "
							f"from {r_start} to {r_end}."
						))


	def before_submit(self):
		overtime_details_data=frappe.db.get_all("Overtime Details",filters={"parent":self.name},fields=['employee','hourly_ot'])
		for od in overtime_details_data:
			employee=od['employee']
			hourly_ot=od['hourly_ot']
			attendance_data=frappe.db.get_all("Attendance",filters=[['attendance_date','>=',self.from_date],['attendance_date','<=',self.to_date],['employee','=',employee]],fields=['name','custom_overtime_checkin'])
			if attendance_data:
				for attendance in attendance_data:
					frappe.db.set_value('Attendance',attendance['name'], 'custom_overtimemarked_in_system',hourly_ot)
					if hourly_ot<attendance['custom_overtime_checkin']:
						frappe.db.set_value('Attendance',attendance['name'], 'custom_effective_overtime_duration',hourly_ot)
					else:
						frappe.db.set_value('Attendance',attendance['name'], 'custom_effective_overtime_duration',attendance['custom_overtime_checkin'])

	def before_cancel(self):
		overtime_details_data=frappe.db.get_all("Overtime Details",filters={"parent":self.name},fields=['employee'])
		for od in overtime_details_data:
			employee=od['employee']
			attendance_data=frappe.db.get_all("Attendance",filters=[['attendance_date','>=',self.from_date],['attendance_date','<=',self.to_date],['employee','=',employee]],fields=['name','custom_overtime_checkin'])
			if attendance_data:
				for attendance in attendance_data:
					frappe.db.set_value('Attendance',attendance['name'], 'custom_overtimemarked_in_system',0)
					frappe.db.set_value('Attendance',attendance['name'], 'custom_effective_overtime_duration',0)





	@frappe.whitelist()
	def fill_employee_details(self):
		self.set('employees', [])
		employees = self.get_emp_list()
		print(employees)
		if not employees:
			error_msg = _("No employees found for the mentioned criteria:")
			if self.primary_department:
				error_msg += "<br>" + _("Primary Department: {0}").format(frappe.bold(self.primary_department))
			if self.primary_designation:
				error_msg += "<br>" + _("Primary Designation: {0}").format(frappe.bold(self.primary_designation))
			if self.employment_type:
				error_msg += "<br>" + _("Employment Type: {0}").format(frappe.bold(self.employment_type))
			frappe.throw(error_msg, title=_("No employees found"))

		for d in employees:
			print(d)
			d['hourly_ot'] = self.hourly_ot
			self.append('employees', d)

		self.number_of_employees = len(self.employees)

	def get_emp_list(self):
		"""
			Returns list of active employees based on selected criteria
			and for which salary structure exists
		"""
		# self.check_mandatory()
		filters = self.make_filters()
		cond = get_filter_condition(filters)
	
		emp_list = get_emp_list(self, cond)

		return emp_list

	def make_filters(self):
		filters = frappe._dict()
		filters['department'] = self.primary_department
		filters['designation'] = self.primary_designation
		filters['employment_type'] = self.employment_type

		return filters
	def check_ot_eligibility(self):
		invalid_employees = []

		for emp_row in self.employees:
			employee = emp_row.employee

			# fetch required info
			emp_info = frappe.db.get_value(
				"Employee",
				employee,
				["custom_ot_applicable", "default_shift", "employee_name"],
				as_dict=True
			)

			if not emp_info:
				invalid_employees.append(f"{employee} (Employee Not Found)")
				continue

			# check if employee marked OT applicable
			if emp_info.custom_ot_applicable != "Yes":
				invalid_employees.append(
					f"{emp_info.employee_name or employee} (OT Not Applicable)"
				)
				continue

			# check shift type allows overtime
			if emp_info.default_shift:
				allow_ot = frappe.db.get_value(
					"Shift Type", emp_info.default_shift, "custom_allow_overtime"
				)
				if not allow_ot:
					invalid_employees.append(
						f"{emp_info.employee_name or employee} (Shift Does Not Allow OT)"
					)
			else:
				invalid_employees.append(
					f"{emp_info.employee_name or employee} (No Shift Assigned)"
				)

		# if any invalid found, stop saving
		if invalid_employees:
				frappe.throw(_(
				"The following employees are not eligible for Overtime:<br>"
				+ "<br>".join([f"- {frappe.bold(e)}" for e in invalid_employees])
				))

	
	@frappe.whitelist()
	def set_hourly_ot(self):
		employees = self.employees
		for emp in employees:
			emp.hourly_ot = self.hourly_ot

def get_filter_condition(filters):
	cond = ''
	for f in [ 'department', 'designation','employment_type']:
		if filters.get(f):
			cond += " and t1." + f + " = " + frappe.db.escape(filters.get(f))

	return cond

def get_emp_list(self, cond):
	print(cond)
	return frappe.db.sql("""
		SELECT DISTINCT t1.name AS employee, t1.employee_name, t1.department 
		FROM `tabEmployee` t1 
		JOIN `tabShift Type` st
		on t1.default_shift=st.name 
		WHERE st.custom_allow_overtime = 1 and  t1.custom_ot_applicable = 'Yes'
			AND (
				t1.status = 'Active'
				OR (t1.status = 'Left' AND t1.relieving_date >= %(from_date)s)
			)
			AND t1.name != %(excluded_employee)s
	""" + cond, {
		"from_date": self.from_date,
		"excluded_employee": self.apply_byemployee_name
	}, as_dict=True)

