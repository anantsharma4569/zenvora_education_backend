import frappe
from frappe import _
from frappe.query_builder import DocType

from zenvora_education.api.utils import get_instructor_student_groups, is_admin


@frappe.whitelist()
def get_staff_directory(company=None, status="Active"):
	"""Employees (Active by default; pass status="Inactive" or "all") split into teaching_staff / non_teaching_staff based on
	whether their Designation has `is_teaching_role` checked.

	Returns:
	    {
	        "teaching_staff": [{employee, employee_name, designation, department, status, is_teaching_role}, ...],
	        "non_teaching_staff": [...],
	    }
	"""
	if not is_admin():
		frappe.throw(_("Not authorized to view the staff directory"))

	Employee = DocType("Employee")
	Designation = DocType("Designation")

	query = (
		frappe.qb.from_(Employee)
		.inner_join(Designation)
		.on(Employee.designation == Designation.name)
		.select(
			Employee.name.as_("employee"),
			Employee.employee_name,
			Employee.designation,
			Employee.department,
			Employee.status,
			Employee.personal_email,
			Employee.date_of_joining,
			Employee.user_id,
			Designation.is_teaching_role,
		)
	)
	if status != "all":
		query = query.where(Employee.status == ("Inactive" if status == "Inactive" else "Active"))
	if company:
		query = query.where(Employee.company == company)

	rows = query.run(as_dict=True)
	for row in rows:
		row.is_teaching_role = bool(row.is_teaching_role)
		row.has_login = bool(row.user_id)
		row.date_of_joining = str(row.date_of_joining) if row.date_of_joining else None

	teaching_staff = [row for row in rows if row.is_teaching_role]
	non_teaching_staff = [row for row in rows if not row.is_teaching_role]
	return {"teaching_staff": teaching_staff, "non_teaching_staff": non_teaching_staff}


@frappe.whitelist()
def list_designations():
	"""All Designations with their is_teaching_role flag, for the Add Staff form's
	dropdown (teaching ones first). Admin-only, like the rest of staff management."""
	if not is_admin():
		frappe.throw(_("Not authorized to view designations"))

	rows = frappe.get_all(
		"Designation", fields=["name", "is_teaching_role"], order_by="name", ignore_permissions=True
	)
	rows.sort(key=lambda r: (not r.is_teaching_role, r.name))
	return [{"name": r.name, "is_teaching_role": bool(r.is_teaching_role)} for r in rows]


@frappe.whitelist()
def is_employee_teaching_staff(employee):
	"""True if `employee`'s Designation is flagged is_teaching_role, else False.

	Used directly (not just over HTTP) by the Instructor.validate doc_event hook.
	"""
	designation = frappe.db.get_value("Employee", employee, "designation")
	if not designation:
		return False
	return bool(frappe.db.get_value("Designation", designation, "is_teaching_role"))


def warn_if_not_teaching_designation(doc, method=None):
	"""doc_events hook for Instructor.validate - a hint, not a hard block: an
	Instructor linked to an Employee whose Designation isn't marked as a
	teaching role is unusual but not necessarily wrong (e.g. a Principal who
	also teaches, before their Designation is flagged).
	"""
	if not doc.employee:
		return
	if not is_employee_teaching_staff(doc.employee):
		frappe.msgprint(
			_("This employee's designation is not marked as a teaching role."),
			indicator="orange",
		)


@frappe.whitelist()
def get_employee_detail(employee):
	"""Everything about one staff member for the detail page: profile, teaching status
	and sections (if an instructor), an attendance summary and login status.

	Admin-only, like the rest of staff management (get_staff_directory).
	"""
	if not is_admin():
		frappe.throw(_("Not authorized to view staff records"))

	doc = frappe.get_doc("Employee", employee)
	designation_teaching = bool(
		frappe.db.get_value("Designation", doc.designation, "is_teaching_role") if doc.designation else False
	)
	instructor = frappe.db.get_value("Instructor", {"employee": employee}, "name")
	sections = sorted(set(get_instructor_student_groups(instructor))) if instructor else []

	attendance_rows = frappe.get_all(
		"Attendance", filters={"employee": employee}, fields=["status"], ignore_permissions=True
	)
	attendance_counts = {"Present": 0, "Absent": 0, "On Leave": 0, "Half Day": 0, "Work From Home": 0}
	for row in attendance_rows:
		attendance_counts[row.status] = attendance_counts.get(row.status, 0) + 1
	marked = attendance_counts["Present"] + attendance_counts["Absent"] + attendance_counts["Half Day"]

	return {
		"name": doc.name,
		"employee_name": doc.employee_name,
		"first_name": doc.first_name,
		"last_name": doc.last_name or "",
		"gender": doc.gender or "",
		"date_of_birth": str(doc.date_of_birth or ""),
		"date_of_joining": str(doc.date_of_joining or ""),
		"status": doc.status,
		"department": doc.department or "",
		"designation": doc.designation or "",
		"company": doc.company or "",
		"personal_email": doc.personal_email or "",
		"cell_number": doc.cell_number or "",
		"current_address": doc.current_address or "",
		"blood_group": doc.blood_group or "",
		"marital_status": doc.marital_status or "",
		"image": doc.image or None,
		"has_login": bool(doc.user_id),
		"is_teaching_role": designation_teaching,
		"instructor": instructor,
		"sections": sections,
		"attendance": {
			"present": attendance_counts["Present"],
			"absent": attendance_counts["Absent"],
			"on_leave": attendance_counts["On Leave"],
			"marked": marked,
			"percent": round(attendance_counts["Present"] / marked * 100, 1) if marked else None,
		},
	}
