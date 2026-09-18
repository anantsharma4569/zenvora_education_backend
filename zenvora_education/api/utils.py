from contextlib import contextmanager

import frappe

ADMIN_ROLES = {"System Manager", "Education Manager"}
ACCOUNTS_ROLES = {"Accounts Manager", "Accounts User"}


def is_admin(user=None):
	roles = frappe.get_roles(user or frappe.session.user)
	return bool(ADMIN_ROLES & set(roles))


def is_accounts(user=None):
	roles = frappe.get_roles(user or frappe.session.user)
	return bool(ACCOUNTS_ROLES & set(roles))


def get_current_employee(user=None):
	return frappe.db.get_value("Employee", {"user_id": user or frappe.session.user}, "name")


def get_current_instructor(user=None):
	employee = get_current_employee(user)
	if not employee:
		return None
	return frappe.db.get_value("Instructor", {"employee": employee}, "name")


def get_current_student(user=None):
	return frappe.db.get_value("Student", {"user": user or frappe.session.user}, "name")


def get_instructor_student_groups(instructor):
	return frappe.get_all(
		"Student Group Instructor",
		filters={"instructor": instructor},
		pluck="parent",
		ignore_permissions=True,
	)


def get_student_groups_for_student(student):
	return frappe.get_all(
		"Student Group Student",
		filters={"student": student, "active": 1},
		pluck="parent",
		ignore_permissions=True,
	)


@contextmanager
def as_administrator():
	"""Temporarily elevate to Administrator for internal Frappe/Education-app hooks
	that do their own privileged inserts outside our control (e.g. Student.validate_user
	creating a linked User, Fee Category.after_insert creating a linked Item) - these run
	under frappe.session.user and ignore the ignore_permissions flag passed to our own
	top-level insert() call. Only use inside functions that already gate access via
	is_admin()/is_accounts()/etc - this is a privilege escalation, not a permission check.
	"""
	original_user = frappe.session.user
	original_sid = frappe.session.sid
	original_data = frappe.session.data
	frappe.set_user("Administrator")
	try:
		yield
	finally:
		frappe.set_user(original_user)
		# frappe.set_user() overwrites session.sid with the *username* and blanks
		# session.data. Frappe persists the session from those at the end of the
		# request, so without restoring them the real session record is clobbered
		# and the caller is logged out on their next request.
		frappe.session.sid = original_sid
		frappe.session.data = original_data
