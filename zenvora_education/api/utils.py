import frappe

ADMIN_ROLES = {"System Manager", "Education Manager"}


def is_admin(user=None):
	roles = frappe.get_roles(user or frappe.session.user)
	return bool(ADMIN_ROLES & set(roles))


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
	)


def get_student_groups_for_student(student):
	return frappe.get_all(
		"Student Group Student",
		filters={"student": student, "active": 1},
		pluck="parent",
	)
