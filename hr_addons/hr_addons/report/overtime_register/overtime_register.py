import frappe
from frappe.utils import getdate
from datetime import timedelta

def execute(filters=None):
    columns = get_columns(filters)
    data = get_data(filters)
    return columns, data

def daterange(start_date, end_date):
    for n in range(int((end_date - start_date).days) + 1):
        yield start_date + timedelta(n)

def get_columns(filters):
    columns = [
        {"label": "Employee Name", "fieldname": "employee_name", "fieldtype": "Data", "width": 180, "align": "left"},
        {"label": "Employee Code", "fieldname": "employee", "fieldtype": "Data", "options": "Employee", "width": 120, "align": "left"},
        {"label": "Department", "fieldname": "department", "fieldtype": "Data", "width": 130, "align": "left"},
    ]

    # Date-wise OT columns
    from_date = getdate(filters.get("from_date"))
    to_date = getdate(filters.get("to_date"))
    for dt in daterange(from_date, to_date):
        label = dt.strftime("%d-%b")
        fieldname = dt.strftime("ot_%Y_%m_%d")
        columns.append({
            "label": f"{label}",
            "fieldname": fieldname,
            "fieldtype": "Data",
            "width": 100,
            "align": "left"
        })

    # Add total OT, OT rate, and total incentive
    columns.extend([
        {"label": "Total OT Hours", "fieldname": "total_ot", "fieldtype": "Data", "width": 120, "align": "left"},
        {"label": "OT Rate", "fieldname": "ot_rate", "fieldtype": "Currency", "width": 100, "align": "left"},
        {"label": "Total Incentive", "fieldname": "total_incentive", "fieldtype": "Currency", "width": 140, "align": "left"},
    ])

    return columns

def get_data(filters):
    from_date = getdate(filters.get("from_date"))
    to_date = getdate(filters.get("to_date"))
    date_list = list(daterange(from_date, to_date))

    # Build condition dynamically
    conditions = ["a.docstatus = 1"]
    values = {}

    if filters.get("employee"):
        conditions.append("a.employee = %(employee)s")
        values["employee"] = filters["employee"]
    if filters.get("department"):
        conditions.append("e.department = %(department)s")
        values["department"] = filters["department"]
    if filters.get("employment_type"):
        if isinstance(filters["employment_type"], list):
            conditions.append("e.employment_type IN %(employment_type)s")
            values["employment_type"] = tuple(filters["employment_type"])
        else:
            conditions.append("e.employment_type = %(employment_type)s")
            values["employment_type"] = filters["employment_type"]
    if filters.get("designation"):
        if isinstance(filters["designation"], list):
            conditions.append("e.designation IN %(designation)s")
            values["designation"] = tuple(filters["designation"])
        else:
            conditions.append("e.designation = %(designation)s")
            values["designation"] = filters["designation"]

    conditions.append("a.attendance_date BETWEEN %(from_date)s AND %(to_date)s")
    values["from_date"] = from_date
    values["to_date"] = to_date

    condition_str = " AND ".join(conditions)

    attendance_data = frappe.db.sql(f"""
        SELECT 
            a.employee,
            e.employee_name,
            a.attendance_date,
            e.department,
            SUM(IFNULL(a.custom_effective_overtime_duration, 0)) AS effective_ot,
            (
                SELECT ssa.custom_ot_amount_calculation
                FROM `tabSalary Structure Assignment` ssa
                WHERE ssa.employee = a.employee
                  AND ssa.from_date <= a.attendance_date
                  AND ssa.docstatus = 1
                ORDER BY ssa.from_date DESC
                LIMIT 1
            ) AS ot_amount_calculation,
                (
                SELECT ssa.custom_standard_multiplier
                FROM `tabSalary Structure Assignment` ssa
                WHERE ssa.employee = a.employee
                AND ssa.from_date <= a.attendance_date
                AND ssa.docstatus = 1
                ORDER BY ssa.from_date DESC
                LIMIT 1
            ) AS ot_standard_multiplier,
            (
                SELECT ssa.base
                FROM `tabSalary Structure Assignment` ssa
                WHERE ssa.employee = a.employee
                  AND ssa.from_date <= a.attendance_date
                  AND ssa.docstatus = 1
                ORDER BY ssa.from_date DESC
                LIMIT 1
            ) AS gross_pay,
            (
                SELECT ss.total_working_days
                FROM `tabSalary Slip` ss
                WHERE ss.employee = a.employee
                  AND a.attendance_date BETWEEN ss.start_date AND ss.end_date
                  AND ss.docstatus in (1,0)
                ORDER BY ss.posting_date DESC
                LIMIT 1
            ) AS total_working_days
        FROM `tabAttendance` a
        JOIN `tabEmployee` e ON a.employee = e.name
        WHERE {condition_str}
        GROUP BY a.employee, a.attendance_date
    """, values, as_dict=True)
    # Process data into a map
    employee_map = {}
    for row in attendance_data:
        emp = row["employee"]
        date_key = row["attendance_date"].strftime("ot_%Y_%m_%d")
        ot_amount_calculation = row["ot_amount_calculation"] 
        effective_ot = row["effective_ot"] or 0.0
        ot_standard_multiplier=row["ot_standard_multiplier"] or 1.0
        incentive = 0.0
        ot_rate=0.0
        rate=0.0

        print("row[gross_pay] :: " , row,ot_amount_calculation,row["total_working_days"])
        print(emp, ot_amount_calculation, ot_rate, effective_ot)
        
        if ot_amount_calculation=="Salary Component Based":
               ot_rate=0.0
               if row["gross_pay"] and row["total_working_days"] and row["total_working_days"] != 0:
                    rate = (row["gross_pay"] / row["total_working_days"])
        elif ot_amount_calculation=="Fixed Hourly Rate":
                rate = frappe.db.get_value("Salary Structure Assignment", {"employee": emp, "docstatus": 1},"custom_ot_rate")
                ot_rate=rate
        else:
                ot_rate=0.0
                rate=0.0

        incentive = rate * (effective_ot/8)*(ot_standard_multiplier)
        print(emp, ot_amount_calculation, ot_rate, effective_ot)
        if emp not in employee_map:
            employee_map[emp] = {
                "employee": emp,
                "employee_name": row["employee_name"],
                "department": row["department"],
                "total_ot": 0.0,
                "ot_rate": ot_rate,
                "total_incentive": 0.0,
            }

        employee_map[emp][date_key] = effective_ot
        employee_map[emp]["total_ot"] += effective_ot
        employee_map[emp]["total_incentive"] += incentive

    # Final output
    data = []
    date_totals = {dt.strftime("ot_%Y_%m_%d"): 0.0 for dt in date_list}
    grand_total_ot = 0.0
    grand_total_incentive = 0.0
    for idx, emp_data in enumerate(employee_map.values(), start=1):
        emp_data["index"] = idx

        for date_key in date_totals:
            if date_key not in emp_data:
                emp_data[date_key] = 0.0
            date_totals[date_key] += emp_data[date_key]

        grand_total_ot += emp_data.get("total_ot", 0.0)
        grand_total_incentive += emp_data.get("total_incentive", 0.0)
        data.append(emp_data)

    # Add Grand Total row
    print("**************************",grand_total_ot,grand_total_incentive)
    total_row = {
        "employee_name": "Total",
        "employee": "",
        "department": "",
        "total_ot": grand_total_ot,
        "ot_rate": "",
        "total_incentive": grand_total_incentive,
        "index": "",
    }

    for date_key, total in date_totals.items():
        total_row[date_key] = total

    data.append(total_row)

    return data
