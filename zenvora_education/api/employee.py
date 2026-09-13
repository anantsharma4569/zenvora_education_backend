import frappe
from frappe import _


@frappe.whitelist()
def create_employee(
	employee_name,
	department,
	designation,
	date_of_joining,
	company,
	personal_email=None,
	is_instructor=0,
):
	"""Create an Employee, and optionally link it as an Instructor in one step."""
	if not frappe.has_permission("Employee", "create"):
		frappe.throw(_("Not permitted to create Employee records"))

	employee = frappe.get_doc(
		{
			"doctype": "Employee",
			"employee_name": employee_name,
			"department": department,
			"designation": designation,
			"date_of_joining": date_of_joining,
			"company": company,
			"personal_email": personal_email,
			"status": "Active",
		}
	)
	employee.insert()

	instructor_name = None
	if int(is_instructor):
		instructor = frappe.get_doc(
			{
				"doctype": "Instructor",
				"instructor_name": employee_name,
				"employee": employee.name,
				"status": "Active",
			}
		)
		instructor.insert()
		instructor_name = instructor.name

	return {"employee": employee.name, "instructor": instructor_name}


@frappe.whitelist()
def list_employees(department=None):
	filters = {}
	if department:
		filters["department"] = department
	return frappe.get_all(
		"Employee",
		filters=filters,
		fields=["name", "employee_name", "department", "designation", "status"],
		order_by="employee_name",
	)
