import frappe
from frappe import _
from frappe.query_builder import DocType

from zenvora_education.api.utils import is_admin


@frappe.whitelist()
def get_staff_directory(company=None):
	"""Active Employees split into teaching_staff / non_teaching_staff based on
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
			Designation.is_teaching_role,
		)
		.where(Employee.status == "Active")
	)
	if company:
		query = query.where(Employee.company == company)

	rows = query.run(as_dict=True)
	for row in rows:
		row.is_teaching_role = bool(row.is_teaching_role)

	teaching_staff = [row for row in rows if row.is_teaching_role]
	non_teaching_staff = [row for row in rows if not row.is_teaching_role]
	return {"teaching_staff": teaching_staff, "non_teaching_staff": non_teaching_staff}


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
