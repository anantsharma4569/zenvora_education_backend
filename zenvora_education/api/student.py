import frappe
from frappe import _

from zenvora_education.api.utils import (
	get_current_instructor,
	get_instructor_student_groups,
	is_accounts,
	is_admin,
)


@frappe.whitelist()
def list_students(search=None):
	"""Admin/Accounts: all enabled students (optionally filtered by name search).
	Teacher: only students in their assigned Student Groups.
	"""
	if is_admin() or is_accounts():
		filters = {"enabled": 1}
		if search:
			filters["student_name"] = ["like", f"%{search}%"]
		return frappe.get_all(
			"Student",
			filters=filters,
			fields=["name", "student_name", "student_email_id", "enabled"],
			order_by="student_name",
		)

	instructor = get_current_instructor()
	if not instructor:
		frappe.throw(_("Not authorized to view students"))

	allowed_groups = get_instructor_student_groups(instructor)
	if not allowed_groups:
		return []

	student_names = frappe.get_all(
		"Student Group Student",
		filters={"parent": ["in", allowed_groups], "active": 1},
		pluck="student",
	)
	if not student_names:
		return []

	return frappe.get_all(
		"Student",
		filters={"name": ["in", student_names], "enabled": 1},
		fields=["name", "student_name"],
		order_by="student_name",
	)
