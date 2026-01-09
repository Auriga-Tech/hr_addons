import frappe
import datetime
from datetime import timedelta
from hrms.hr.doctype.attendance.attendance import Attendance as BaseAttendance
from frappe.utils import time_diff_in_hours, get_datetime, flt
from hr_addons.utils.gatepass_utils import update_attendance_status_based_on_threshold, round_time_based_on_setting

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

def validate(doc,method):
    set_daily_overtime(doc,method)
    apply_gatepass_deduction(doc,method)

def calculate_working_hours(employee_shift=None, attendance_date=None, in_time=None, out_time=None):
    try:
        if in_time and out_time:
            attendance_checkin_time = datetime.datetime.strptime(str(in_time), "%Y-%m-%d %H:%M")
            attendance_checkout_time = datetime.datetime.strptime(str(out_time), "%Y-%m-%d %H:%M")
            
            shift_start_time = datetime.datetime.strptime(str(attendance_date) + " " + str(employee_shift.start_time), "%Y-%m-%d %H:%M:%S")
            shift_end_time = datetime.datetime.strptime(str(attendance_date) + " " + str(employee_shift.end_time), "%Y-%m-%d %H:%M:%S")
            
            # Adjust check-in and check-out to within shift timings
            actual_check_in = max(attendance_checkin_time, shift_start_time)
            actual_check_out = min(attendance_checkout_time, shift_end_time)
            print("calculate working hours",attendance_checkin_time,attendance_checkin_time,actual_check_in,actual_check_out)
            # Calculate working hours
            if actual_check_out > actual_check_in:
                working_hours = (actual_check_out - actual_check_in).total_seconds() / 3600
                print("if",working_hours)
            else:
                working_hours = 0
            print("working",working_hours)
            return working_hours
    except Exception as e:
        frappe.log_error(f"Error in calculate_working_hours: {str(e)}", "Working Hours Calculation Error")

def get_daily_ot(employee=None, employee_shift=None, attendance_date=None, in_time=None, out_time=None, deduction_hours=0):
    overtime = 0
    evening_diff = 0  # Initialize here
    morning_diff = 0 
    try:
        if in_time and out_time:
            attendance_checkin_time = datetime.datetime.strptime(str(in_time), "%Y-%m-%d %H:%M")
            attendance_checkout_time = datetime.datetime.strptime(str(out_time), "%Y-%m-%d %H:%M")
            print("get_daily_ot",attendance_checkin_time,attendance_checkout_time)
            # Adjust working time based on deduction hours
            working_time = attendance_checkout_time - attendance_checkin_time
            working_time_in_minutes = working_time.total_seconds() / 60 if working_time else 0
            
            shift_start_time = datetime.datetime.strptime(str(attendance_date) + " " + str(employee_shift.start_time), "%Y-%m-%d %H:%M:%S")
            shift_end_time = datetime.datetime.strptime(str(attendance_date) + " " + str(employee_shift.end_time), "%Y-%m-%d %H:%M:%S")
            print("shifttime",shift_start_time,shift_end_time)
            
            shift_time_in_minutes = (shift_end_time - shift_start_time).total_seconds() / 60
            overtime_type=frappe.db.get_value("Shift Type",employee_shift,"custom_overtime_type")
            if_calulate_morning_diff=frappe.db.get_value("Overtime Type",overtime_type,"custom_allow_overtime_before_checkin")
            if_calulate_evening_shift=frappe.db.get_value("Overtime Type",overtime_type,"custom_allow_overtime_after_checkout")
            print("checkout time",(attendance_checkout_time - shift_end_time).total_seconds() / 60,(shift_start_time-attendance_checkin_time).total_seconds() / 60)
            if(if_calulate_evening_shift):
                print("in ig")
                overtime=0
                evening_diff = max(0, (attendance_checkout_time - shift_end_time).total_seconds() / 60)
                print("eve",evening_diff)
                evening_late = shift_end_time < attendance_checkout_time
                overtime = evening_diff if evening_late else 0 
            elif(if_calulate_morning_diff):
                overtime=0
                print("elsif")
                morning_diff= max(0, (shift_start_time-attendance_checkin_time).total_seconds() / 60)
                morning_late = shift_start_time > attendance_checkin_time
                overtime = morning_diff if morning_late else 0
            if(if_calulate_morning_diff and if_calulate_evening_shift):
                overtime=0
                print("bothif")
                evening_late = shift_end_time < attendance_checkout_time                
                morning_late = shift_start_time > attendance_checkin_time

                if morning_late:
                    morning_diff= max(0, (shift_start_time-attendance_checkin_time).total_seconds() / 60)
                    print("mor",morning_diff)
                    overtime += morning_diff

                if evening_late:
                    evening_diff = max(0, (attendance_checkout_time - shift_end_time).total_seconds() / 60)
                    print("vev",evening_diff)
                    overtime += evening_diff
            
            print("testttrooooo",evening_diff,morning_diff,evening_diff+morning_diff,overtime)
            # late_entry_grace_in_minutes = employee_shift.late_entry_grace_period
            # early_exit_grace_in_minutes = employee_shift.early_exit_grace_period
            
            
            
            working_hours = working_time_in_minutes / 60
            return get_calculated_ot(overtime)
    except Exception as e:
        frappe.log_error(f"Error in get_daily_ot: {str(e)}", "Overtime Calculation Error")

    return get_calculated_ot(overtime)

def get_calculated_ot(minutes):
    try:
           
        hourly_ot=0
        # Subtract the initial hour
        remaining_minutes = minutes 
        hourly_ot=remaining_minutes/60
        
        # print("remaing_minutes",remaining_minutes)
        # # Calculate how many half-hour blocks are completed
        # half_hours = remaining_minutes // 30
        # remainder = remaining_minutes % 30
        # print("half",half_hours,remainder)
        # # Add completed half-hour blocks
        # hourly_ot += half_hours * 0.5

        # # Only round up to the next half hour if remainder completes a half hour
        # if remainder    :
        #     hourly_ot += (remainder/30)
        #     print("hourly_ot",hourly_ot)

        return hourly_ot
    except Exception as e:
        frappe.log_error(f"Error in get_calculated_ot: {str(e)}", "OT Calculation Error")
        return 0

# def updateLateEntry(self):
    # if self.late_entry:
    #     self.custom_islateentry = 0
    #     if self.custom_late_entry_count == 0:
    #         self.custom_late_entry_count = 2
    #     else:
    #         self.custom_late_entry_count = self.custom_late_entry_count - 1

# def updateGatepass(self, emp_shift, short_leave_count=0, working_hours=0):
#     try:
#         attendance_date = self.attendance_date
        
#         # Convert attendance_date to datetime format for comparison
#         attendance_start = datetime.datetime.strptime(str(attendance_date) + " 00:00:00", "%Y-%m-%d %H:%M:%S")
#         attendance_end = datetime.datetime.strptime(str(attendance_date) + " 23:59:59", "%Y-%m-%d %H:%M:%S")

#         # Fetch Gatepass records for the attendance date
#         gatepass_records = frappe.get_all(
#             "Gatepass",
#             filters={
#                 "employee": self.employee,
#                 "type": "Personal",
#                 "docstatus":1,
#                 "out_time": ["between", [attendance_start, attendance_end]]
#             },
#             fields=["in_time", "out_time", "status", "type", "attendance_marked", "name"]
#         )

#         if not gatepass_records:
#             return

#         # Calculate deduction hours, first out time, and last in time
#         total_deduction_minutes = 0
#         gp_in_time = max([gp["in_time"] for gp in gatepass_records if gp["in_time"]])
#         gp_out_time = min([gp["out_time"] for gp in gatepass_records if gp["out_time"]])

#         for gatepass in gatepass_records:
#             if gatepass["in_time"] and gatepass["out_time"]:
#                 deduction_minutes = (gatepass["in_time"] - gatepass["out_time"]).total_seconds() / 60
#                 total_deduction_minutes += max(deduction_minutes, 0)

#         deduction_hours = total_deduction_minutes / 60

#         # Handle short leave or half-day status
#         gp_status = ""
#         if self.status != "Absent":
#             if self.custom_short_leave == 1 and self.late_entry:
#                 updateLateEntry(self)
#                 self.custom_short_leave = 0
#                 self.custom_short_leave_count = max(0, short_leave_count - 1)
#                 self.status = "Half Day"
#                 gp_status = "Half Day"
#             elif deduction_minutes <= 120:
#                 if self.custom_short_leave == 0:
#                     self.custom_short_leave_count = short_leave_count + 1
#                 self.status = "Half Day" if self.custom_short_leave_count > 2 else self.status
#                 gp_status = "Short Leave"
#                 self.custom_short_leave = 1
#             elif working_hours < emp_shift.working_hours_threshold_for_half_day  or 120 < deduction_minutes <= 240:
#                 updateLateEntry(self)
#                 self.status = "Half Day"
#                 gp_status = "Half Day"
#             elif deduction_minutes > 240 or working_hours < emp_shift.working_hours_threshold_for_absent:
#                 updateLateEntry(self)
#                 self.status = "Absent"
#                 gp_status = "Absent"


#         # Update attendance values
#         self.custom_deduction_hours = deduction_hours
#         self.custom_intime = gp_in_time
#         self.custom_outtime = gp_out_time
#         self.custom_gatepass_status = gp_status
#         self.custom_gatepass = gatepass["name"]

#         # Update Gatepass records
#         for gatepass in gatepass_records:
#             frappe.db.set_value("Gatepass", gatepass["name"], {
#                 "status": gp_status,
#                 "attendance_marked": self.name
#             })

#     except Exception as e:
#         frappe.log_error(f"Error in updateGatepass: {str(e)}", "Update Error in Gatepass")

@frappe.whitelist()
def set_daily_overtime(self, method=None):
    try:
        attendance_date = self.attendance_date
        print("attendance date",attendance_date)
        if self.in_time and not self.out_time:
            self.status = "Half Day"
            return
        if self.in_time and self.out_time:
            first_checkin = datetime.datetime.strptime(str(self.in_time),"%Y-%m-%d %H:%M:%S")
            last_checkout = datetime.datetime.strptime(str(self.out_time),"%Y-%m-%d %H:%M:%S")
            print("first_checin",first_checkin,last_checkout)
            # assigned_shift = frappe.db.get_value(
            # "Shift Assignment",
            # {
            #     "employee": self.employee,
            #     "start_date": ("<=", self.attendance_date),
            #     "end_date": (">=", self.attendance_date),
            #     "docstatus": 1
            # },
            # "shift_type"
            # )
            # if assigned_shift:
            #     emp_shift=assigned_shift
            # else:
            emp_shift = frappe.get_doc("Shift Type",self.shift)
           
            in_time = first_checkin.strftime("%Y-%m-%d")+ " " + first_checkin.strftime("%H:%M")
            out_time = first_checkin.strftime("%Y-%m-%d")+ " " + last_checkout.strftime("%H:%M")
            print("in_time",in_time,out_time)
    
            ot_time  = get_daily_ot(employee = self.employee,
                        employee_shift = emp_shift,
                        attendance_date = first_checkin.strftime("%Y-%m-%d"),
                        in_time=in_time,
                        out_time=out_time)
            print("***********",self.employee, self.attendance_date, self.attendance_date)
            overtime = frappe.db.sql("""select od.hourly_ot
                                            from `tabOvertime Details` od join `tabOvertime` o 
                                            on o.name=od.parent 
                                            where od.employee = '{}' 
                                            and o.docstatus = 1
                                            and o.from_date <= '{}' and o.to_date >= '{}';
                            """.format(self.employee, self.attendance_date, self.attendance_date), as_dict=True)
            print("ot_time",ot_time,overtime)
            print("888888888888*************************************************",emp_shift,emp_shift.custom_maximum_overtime_hours_allowed)
            working_hours = calculate_working_hours(employee_shift = emp_shift,attendance_date = first_checkin.strftime("%Y-%m-%d"),in_time=in_time,out_time=out_time)
            self.custom_standard_working_hours = working_hours
            print("after working_hours",working_hours,self.custom_standard_working_hours)
            # update the half day based on the late entry or short leave
            shift_start_time = datetime.datetime.strptime(
                str(attendance_date) + " " + str(emp_shift.start_time), "%Y-%m-%d %H:%M:%S"
            )
            print("shift_start_time",shift_start_time)
           
            print("above_overtime")
            print("Above ot_time", ot_time)
            ot_time = float(ot_time)
            print("Under ot_time")
            print("ot_time",ot_time)
            print("overtime",overtime)
           
           
            if overtime:
                
                if overtime[0]['hourly_ot'] > ot_time:
                    self.custom_effective_overtime_duration= ot_time
                    
                    
                else:
                    self.custom_effective_overtime_duration= overtime[0]['hourly_ot']
                self.custom_overtime_checkin = ot_time
                self.custom_overtimemarked_in_system = overtime[0]['hourly_ot']
                print("if overtimr",self.custom_effective_overtime_duration,ot_time)
            if not overtime and self.status != "Absent":
                print("else Absent",ot_time)
                if emp_shift.custom_allow_overtime ==1 and emp_shift.custom_maximum_overtime_hours_allowed:
                    self.custom_overtimemarked_in_system=emp_shift.custom_maximum_overtime_hours_allowed
                    self.custom_overtime_checkin = ot_time
                    self.custom_effective_overtime_duration=min(emp_shift.custom_maximum_overtime_hours_allowed,ot_time)
                else:
                    self.custom_overtime_checkin = ot_time
                    self.custom_overtimemarked_in_system = 0
        

            overtime_type=frappe.db.get_value("Shift Type",self.shift,"custom_overtime_type")
            overtime_source=frappe.db.get_value("Overtime Type",overtime_type,"custom_overtime_source")
            if overtime_source=="Sheet Overtime":
                self.custom_effective_overtime_duration=self.custom_overtime_checkin
            
            

            print("last",self.custom_effective_overtime_duration,self.custom_overtime_checkin,self.custom_overtimemarked_in_system)
    except Exception as e:
        frappe.log_error(f"Error in set_daily_overtime: {str(e)}", "Update Error in Overtime")


@frappe.whitelist()
def apply_gatepass_deduction(doc,method=None):
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
