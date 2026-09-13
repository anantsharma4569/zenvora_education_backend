import frappe
from frappe import _

from zenvora_education.api.utils import is_admin


@frappe.whitelist()
def create_employee(
	first_name,
	gender,
	date_of_birth,
	department,
	designation,
	date_of_joining,
	company,
	last_name=None,
	personal_email=None,
	is_instructor=0,
):
	"""Create an Employee, and optionally link it as an Instructor in one step."""
	if not is_admin():
		frappe.throw(_("Not permitted to create Employee records"))

	employee = frappe.get_doc(
		{
			"doctype": "Employee",
			"first_name": first_name,
			"last_name": last_name,
			"gender": gender,
			"date_of_birth": date_of_birth,
			"department": department,
			"designation": designation,
			"date_of_joining": date_of_joining,
			"company": company,
			"personal_email": personal_email,
			"status": "Active",
		}
	)
	employee.insert(ignore_permissions=True)

	instructor_name = None
	if int(is_instructor):
		instructor = frappe.get_doc(
			{
				"doctype": "Instructor",
				"instructor_name": employee.employee_name,
				"employee": employee.name,
				"status": "Active",
			}
		)
		instructor.insert(ignore_permissions=True)
		instructor_name = instructor.name

	return {"employee": employee.name, "instructor": instructor_name}


@frappe.whitelist()
def list_employees(department=None):
	if not is_admin():
		frappe.throw(_("Not permitted to view Employee records"))

	filters = {}
	if department:
		filters["department"] = department
	return frappe.get_all(
		"Employee",
		filters=filters,
		fields=["name", "employee_name", "department", "designation", "status"],
		order_by="employee_name",
		ignore_permissions=True,
	)
