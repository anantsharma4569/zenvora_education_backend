import frappe
from frappe import _

from zenvora_education.api.utils import (
	get_current_employee,
	get_current_instructor,
	get_current_student,
	get_instructor_student_groups,
	is_admin,
)


@frappe.whitelist()
def get_employee_attendance(employee=None, from_date=None, to_date=None):
	"""Admin: all employees (optionally filtered by `employee`). Everyone else: self only."""
	filters = {}

	if is_admin():
		if employee:
			filters["employee"] = employee
	else:
		self_employee = get_current_employee()
		if not self_employee:
			frappe.throw(_("No Employee record linked to this user"))
		filters["employee"] = self_employee

	if from_date and to_date:
		filters["attendance_date"] = ["between", [from_date, to_date]]

	return frappe.get_all(
		"Attendance",
		filters=filters,
		fields=["name", "employee", "employee_name", "attendance_date", "status", "department"],
		order_by="attendance_date desc",
	)


@frappe.whitelist()
def get_student_attendance(student_group=None, date=None):
	"""Admin: all Student Groups. Instructor: only Student Groups assigned to them. Others: blocked."""
	filters = {}

	if is_admin():
		if student_group:
			filters["student_group"] = student_group
	else:
		instructor = get_current_instructor()
		if not instructor:
			frappe.throw(_("Not authorized to view student attendance"))

		allowed_groups = get_instructor_student_groups(instructor)
		if not allowed_groups:
			return []

		if student_group:
			if student_group not in allowed_groups:
				frappe.throw(_("Not authorized for this Student Group"))
			filters["student_group"] = student_group
		else:
			filters["student_group"] = ["in", allowed_groups]

	if date:
		filters["date"] = date

	return frappe.get_all(
		"Student Attendance",
		filters=filters,
		fields=["name", "student", "student_name", "student_group", "date", "status"],
		order_by="date desc",
	)


@frappe.whitelist()
def get_my_attendance(from_date=None, to_date=None):
	"""Student: own attendance only, no override parameter."""
	student = get_current_student()
	if not student:
		frappe.throw(_("No Student record linked to this user"))

	filters = {"student": student}
	if from_date and to_date:
		filters["date"] = ["between", [from_date, to_date]]

	return frappe.get_all(
		"Student Attendance",
		filters=filters,
		fields=["name", "date", "student_group", "status"],
		order_by="date desc",
	)


@frappe.whitelist()
def mark_student_attendance(student_group, date, attendance):
	"""Instructor (own Student Group only) or Admin: bulk mark attendance.

	`attendance` is a list of {"student": <Student ID>, "status": "Present"|"Absent"|"Leave"}
	"""
	if isinstance(attendance, str):
		attendance = frappe.parse_json(attendance)

	if not is_admin():
		instructor = get_current_instructor()
		if not instructor or student_group not in get_instructor_student_groups(instructor):
			frappe.throw(_("Not authorized to mark attendance for this Student Group"))

	result = []
	for row in attendance:
		existing = frappe.db.get_value(
			"Student Attendance",
			{"student": row["student"], "student_group": student_group, "date": date},
		)
		if existing:
			doc = frappe.get_doc("Student Attendance", existing)
			doc.status = row["status"]
			doc.save(ignore_permissions=True)
		else:
			doc = frappe.get_doc(
				{
					"doctype": "Student Attendance",
					"student": row["student"],
					"student_group": student_group,
					"date": date,
					"status": row["status"],
				}
			)
			doc.insert(ignore_permissions=True)
		result.append(doc.name)

	return result
