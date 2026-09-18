import frappe
from frappe import _

from zenvora_education.api.utils import as_administrator, is_admin

# Frappe roles a staff login gets, by kind of employee. Reuses existing roles
# (no new Roles are created - see project architecture notes).
INSTRUCTOR_ROLES = ["Instructor", "Employee"]
ACCOUNTS_ROLES = ["Accounts User", "Employee"]
STAFF_ROLES = ["Employee"]
ACCOUNTS_DESIGNATIONS = {"Accountant"}


def create_employee_login(employee, password, is_instructor=False):
	"""Create a User for an existing Employee and link it (Employee.user_id).

	Without this the Employee can never log in, so get_current_instructor()
	/ is_accounts() (both keyed off the logged-in user) can't work for them.
	Returns the user's email, or None when the employee has no personal email
	(nothing to log in with) or already has a login.
	"""
	doc = frappe.get_doc("Employee", employee)
	email = doc.personal_email
	if not email or doc.user_id:
		return None

	if is_instructor:
		roles = INSTRUCTOR_ROLES
	elif doc.designation in ACCOUNTS_DESIGNATIONS:
		roles = ACCOUNTS_ROLES
	else:
		roles = STAFF_ROLES

	if frappe.db.exists("User", email):
		frappe.throw(_("A user with email {0} already exists").format(email))

	user = frappe.get_doc(
		{
			"doctype": "User",
			"email": email,
			"first_name": doc.first_name,
			"last_name": doc.last_name,
			"enabled": 1,
			"user_type": "System User",
			"send_welcome_email": 0,
			"new_password": password,
			"roles": [{"role": role} for role in roles],
		}
	)
	# Creating a User (and adding roles) runs hooks that insert further records
	# under the current session user, so it needs a real elevation.
	with as_administrator():
		user.insert(ignore_permissions=True)
		frappe.db.set_value("Employee", employee, "user_id", user.name)
	return user.name


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
	password=None,
):
	"""Create an Employee, and optionally link it as an Instructor in one step.

	If `password` is given (needs `personal_email`), also creates a login for
	them: teachers get the Instructor role, accountants Accounts User, everyone
	else plain Employee.
	"""
	if not is_admin():
		frappe.throw(_("Not permitted to create Employee records"))
	if password and not personal_email:
		frappe.throw(_("A personal email is required to create a login"))

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

	login = create_employee_login(employee.name, password, bool(int(is_instructor))) if password else None

	return {"employee": employee.name, "instructor": instructor_name, "login": login}
