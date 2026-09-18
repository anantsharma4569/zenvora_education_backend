import frappe
from frappe import _

from zenvora_education.api.utils import is_admin


@frappe.whitelist()
def create_course(course_name, department=None, description=None):
	if not is_admin():
		frappe.throw(_("Not permitted to create Course records"))

	course = frappe.get_doc(
		{
			"doctype": "Course",
			"course_name": course_name,
			"department": department,
			"description": description,
		}
	)
	course.insert(ignore_permissions=True)
	return course.name


@frappe.whitelist()
def list_courses(department=None):
	filters = {}
	if department:
		filters["department"] = department
	return frappe.get_all(
		"Course",
		filters=filters,
		fields=["name", "course_name", "department", "description"],
		order_by="course_name",
		ignore_permissions=True,
	)
