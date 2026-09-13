import frappe
from frappe import _

from zenvora_education.api.utils import (
	get_current_instructor,
	get_current_student,
	get_instructor_student_groups,
	is_admin,
)

RESULT_FIELDS = [
	"name",
	"student",
	"student_name",
	"student_group",
	"course",
	"program",
	"academic_year",
	"total_score",
	"maximum_score",
	"grade",
]


@frappe.whitelist()
def get_results(student_group=None):
	"""Admin: all Assessment Results. Instructor: only their Student Groups."""
	filters = {}

	if is_admin():
		if student_group:
			filters["student_group"] = student_group
	else:
		instructor = get_current_instructor()
		if not instructor:
			frappe.throw(_("Not authorized to view results"))

		allowed_groups = get_instructor_student_groups(instructor)
		if not allowed_groups:
			return []

		if student_group:
			if student_group not in allowed_groups:
				frappe.throw(_("Not authorized for this Student Group"))
			filters["student_group"] = student_group
		else:
			filters["student_group"] = ["in", allowed_groups]

	return frappe.get_all(
		"Assessment Result",
		filters=filters,
		fields=RESULT_FIELDS,
		order_by="creation desc",
		ignore_permissions=True,
	)


@frappe.whitelist()
def get_my_results():
	"""Student: own Assessment Results only."""
	student = get_current_student()
	if not student:
		frappe.throw(_("No Student record linked to this user"))

	return frappe.get_all(
		"Assessment Result",
		filters={"student": student},
		fields=RESULT_FIELDS,
		order_by="creation desc",
		ignore_permissions=True,
	)
