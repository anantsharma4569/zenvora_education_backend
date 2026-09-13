import frappe

from zenvora_education.api.utils import (
	get_current_instructor,
	get_current_student,
	get_instructor_student_groups,
	get_student_groups_for_student,
	is_accounts,
	is_admin,
)


@frappe.whitelist()
def get_dashboard():
	if is_admin():
		return _admin_dashboard()

	instructor = get_current_instructor()
	if instructor:
		return _teacher_dashboard(instructor)

	if is_accounts():
		return _accounts_dashboard()

	student = get_current_student()
	if student:
		return _student_dashboard(student)

	frappe.throw("No dashboard available for this user")


def _admin_dashboard():
	return {
		"role": "admin",
		"student_count": frappe.db.count("Student", {"enabled": 1}),
		"employee_count": frappe.db.count("Employee", {"status": "Active"}),
		"instructor_count": frappe.db.count("Instructor", {"status": "Active"}),
		"today_present": frappe.db.count(
			"Student Attendance", {"date": frappe.utils.today(), "status": "Present"}
		),
		"today_absent": frappe.db.count(
			"Student Attendance", {"date": frappe.utils.today(), "status": "Absent"}
		),
	}


def _accounts_dashboard():
	return {
		"role": "accounts",
		"student_count": frappe.db.count("Student", {"enabled": 1}),
	}


def _teacher_dashboard(instructor):
	groups = get_instructor_student_groups(instructor)
	return {
		"role": "teacher",
		"instructor": instructor,
		"student_groups": groups,
	}


def _student_dashboard(student):
	groups = get_student_groups_for_student(student)
	attendance_summary = frappe.get_all(
		"Student Attendance",
		filters={"student": student},
		fields=["status", "count(name) as count"],
		group_by="status",
	)
	return {
		"role": "student",
		"student": student,
		"student_groups": groups,
		"attendance_summary": attendance_summary,
	}
