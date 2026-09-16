import frappe
from frappe import _

from zenvora_education.api.utils import (
	as_administrator,
	get_current_instructor,
	get_instructor_student_groups,
	is_accounts,
	is_admin,
)


def _students_enrolled_in(program):
	"""Student names with a Program Enrollment in `program` (the "class"/grade -
	Student itself has no program field, that only exists via Program Enrollment)."""
	return frappe.get_all(
		"Program Enrollment", filters={"program": program}, pluck="student", ignore_permissions=True
	)


def _students_in_group(student_group):
	"""Student names active in a specific Student Group (the "section", e.g.
	"Grade 3 - B")."""
	return frappe.get_all(
		"Student Group Student",
		filters={"parent": student_group, "active": 1},
		pluck="student",
		ignore_permissions=True,
	)


@frappe.whitelist()
def list_students(search=None, program=None, student_group=None):
	"""Admin/Accounts: all enabled students, optionally filtered by name search,
	Program (class/grade) and/or Student Group (section). Teacher: only
	students in their assigned Student Groups, with the same optional filters.

	`student_group` (a specific section, e.g. "Grade 3 - B") narrows further
	than `program` (the whole grade) - passing both is fine, student_group
	just makes program redundant since a section belongs to one program.
	"""
	if is_admin() or is_accounts():
		filters = {"enabled": 1}
		if search:
			filters["student_name"] = ["like", f"%{search}%"]
		if student_group:
			enrolled = _students_in_group(student_group)
			if not enrolled:
				return []
			filters["name"] = ["in", enrolled]
		elif program:
			enrolled = _students_enrolled_in(program)
			if not enrolled:
				return []
			filters["name"] = ["in", enrolled]
		return frappe.get_all(
			"Student",
			filters=filters,
			fields=["name", "student_name", "student_email_id", "enabled"],
			order_by="student_name",
			ignore_permissions=True,
		)

	instructor = get_current_instructor()
	if not instructor:
		frappe.throw(_("Not authorized to view students"))

	allowed_groups = get_instructor_student_groups(instructor)
	if not allowed_groups:
		return []

	if student_group:
		if student_group not in allowed_groups:
			frappe.throw(_("Not authorized for this Student Group"))
		allowed_groups = [student_group]

	student_names = frappe.get_all(
		"Student Group Student",
		filters={"parent": ["in", allowed_groups], "active": 1},
		pluck="student",
		ignore_permissions=True,
	)
	if not student_names:
		return []

	if program and not student_group:
		enrolled = set(_students_enrolled_in(program))
		student_names = [s for s in student_names if s in enrolled]
		if not student_names:
			return []

	return frappe.get_all(
		"Student",
		filters={"name": ["in", student_names], "enabled": 1},
		fields=["name", "student_name"],
		order_by="student_name",
		ignore_permissions=True,
	)


@frappe.whitelist()
def create_student(
	first_name,
	student_email_id,
	program,
	academic_year,
	last_name=None,
	date_of_birth=None,
	gender=None,
	academic_term=None,
):
	"""Onboard a new student: creates the Student record (which auto-creates
	a Website User with the Student role via the Education app's own
	validate_user hook, unless Education Settings has user creation disabled)
	and enrolls them into a Program for the given Academic Year in one step.
	"""
	if not is_admin():
		frappe.throw(_("Not authorized to create students"))

	student = frappe.get_doc(
		{
			"doctype": "Student",
			"first_name": first_name,
			"last_name": last_name,
			"student_email_id": student_email_id,
			"date_of_birth": date_of_birth,
			"gender": gender,
			"joining_date": frappe.utils.today(),
			"enabled": 1,
		}
	)

	enrollment = frappe.get_doc(
		{
			"doctype": "Program Enrollment",
			"student": None,
			"program": program,
			"academic_year": academic_year,
			"academic_term": academic_term,
			"enrollment_date": frappe.utils.today(),
		}
	)

	# Student.validate() creates a linked User (Education app's own hook) - that
	# insert runs under frappe.session.user regardless of the ignore_permissions
	# passed here, so it needs a real elevation, not just a flag.
	with as_administrator():
		student.insert(ignore_permissions=True)
		enrollment.student = student.name
		enrollment.student_name = student.student_name
		enrollment.insert(ignore_permissions=True)

	return {"student": student.name, "program_enrollment": enrollment.name}
