import frappe
from frappe import _

from zenvora_education.api.utils import (
	as_administrator,
	get_current_instructor,
	get_current_student,
	get_instructor_student_groups,
	get_student_groups_for_student,
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


def _with_placement(rows):
	"""Attach `student_group` (section) and `program` (class) to each row - the
	list shows where a student sits, and Student itself has neither field."""
	if not rows:
		return rows
	members = frappe.get_all(
		"Student Group Student",
		filters={"student": ["in", [r["name"] for r in rows]], "active": 1},
		fields=["student", "parent"],
		ignore_permissions=True,
	)
	group_of = {m.student: m.parent for m in members}
	program_of = dict(
		frappe.get_all(
			"Student Group",
			filters={"name": ["in", list(set(group_of.values()))]},
			fields=["name", "program"],
			as_list=True,
			ignore_permissions=True,
		)
	)
	for r in rows:
		group = group_of.get(r["name"])
		r["student_group"] = group
		r["program"] = program_of.get(group) if group else None
	return rows


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
		return _with_placement(
			frappe.get_all(
				"Student",
				filters=filters,
				fields=["name", "student_name", "student_email_id", "enabled"],
				order_by="student_name",
				ignore_permissions=True,
			)
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

	return _with_placement(
		frappe.get_all(
			"Student",
			filters={"name": ["in", student_names], "enabled": 1},
			fields=["name", "student_name"],
			order_by="student_name",
			ignore_permissions=True,
		)
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
	student_group=None,
):
	"""Onboard a new student: creates the Student record (which auto-creates
	a Website User with the Student role via the Education app's own
	validate_user hook, unless Education Settings has user creation disabled)
	and enrolls them into a Program for the given Academic Year in one step.

	`student_group` (the section, e.g. "Grade 3 - B") is optional but should
	be passed: without it the student sits in a class but in no section, so
	attendance can't be marked for them and section filters never show them.
	"""
	if not is_admin():
		frappe.throw(_("Not authorized to create students"))

	if student_group:
		group_program = frappe.db.get_value("Student Group", student_group, "program")
		if group_program != program:
			frappe.throw(_("Section {0} does not belong to class {1}").format(student_group, program))

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
	#
	# Several of these inserts fire hooks that commit mid-way, so a failure in a
	# later step cannot be undone by rollback alone: the Student can vanish while
	# its Program Enrollment survives, and the next student issued that recycled
	# ID then fails with "Student is already enrolled". Undo explicitly.
	try:
		with as_administrator():
			student.insert(ignore_permissions=True)
			enrollment.student = student.name
			enrollment.student_name = student.student_name
			enrollment.insert(ignore_permissions=True)

			if student_group:
				_add_to_student_group(student_group, student.name, student.student_name)
	except Exception:
		_undo_partial_student(student.name)
		raise

	return {
		"student": student.name,
		"program_enrollment": enrollment.name,
		"student_group": student_group,
	}


def _undo_partial_student(name):
	if not name:
		return
	frappe.db.rollback()
	frappe.db.delete("Student Group Student", {"student": name})
	frappe.db.delete("Program Enrollment", {"student": name})
	if frappe.db.exists("Student", name):
		customer, user = frappe.db.get_value("Student", name, ["customer", "user"])
		frappe.delete_doc("Student", name, force=True, ignore_permissions=True)
		if customer and frappe.db.exists("Customer", customer):
			frappe.delete_doc("Customer", customer, force=True, ignore_permissions=True)
		if user and frappe.db.exists("User", user):
			frappe.delete_doc("User", user, force=True, ignore_permissions=True)
	frappe.db.commit()


def _add_to_student_group(student_group, student, student_name):
	"""Add one member row directly. Saving the whole Student Group would re-run its
	validate() over every existing member, and that check is fragile (it rejects the
	whole section if any single member is inactive)."""
	group = frappe.get_doc("Student Group", student_group)
	members = group.students
	if group.max_strength and len(members) >= group.max_strength:
		frappe.throw(_("Section {0} is full ({1} students)").format(student_group, group.max_strength))
	next_no = max((row.group_roll_number or 0 for row in members), default=0) + 1
	frappe.get_doc(
		{
			"doctype": "Student Group Student",
			"parent": student_group,
			"parenttype": "Student Group",
			"parentfield": "students",
			"idx": len(members) + 1,
			"student": student,
			"student_name": student_name,
			"group_roll_number": next_no,
			"active": 1,
		}
	).insert(ignore_permissions=True)


def _can_view_student(name):
	"""Admin/Accounts: anyone. Teacher: only students in one of their own Student Groups.
	Student: only themselves. Everyone else: no."""
	if is_admin() or is_accounts():
		return True
	instructor = get_current_instructor()
	if instructor:
		allowed = set(get_instructor_student_groups(instructor))
		return bool(allowed & set(get_student_groups_for_student(name)))
	return get_current_student() == name


@frappe.whitelist()
def get_student_detail(name):
	"""Everything about one student for the detail view: profile, guardians, class/section,
	an attendance summary, outstanding fees and the most recent results."""
	if not _can_view_student(name):
		frappe.throw(_("Not authorized to view this student"), frappe.PermissionError)

	doc = frappe.get_doc("Student", name)
	group = frappe.db.get_value("Student Group Student", {"student": name, "active": 1}, "parent")
	program = frappe.db.get_value("Student Group", group, "program") if group else None
	if not program:
		# A student with no section can still have a Program Enrollment.
		program = frappe.db.get_value("Program Enrollment", {"student": name}, "program")

	guardians = []
	for row in doc.guardians:
		g = frappe.db.get_value(
			"Guardian", row.guardian, ["guardian_name", "email_address", "mobile_number"], as_dict=True
		)
		if g:
			guardians.append({"name": row.guardian, "relation": row.relation, **g})

	attendance_rows = frappe.get_all(
		"Student Attendance",
		filters={"student": name},
		fields=["status"],
		ignore_permissions=True,
	)
	attendance_counts = {"Present": 0, "Absent": 0, "Leave": 0}
	for row in attendance_rows:
		attendance_counts[row.status] = attendance_counts.get(row.status, 0) + 1
	marked = attendance_counts["Present"] + attendance_counts["Absent"]

	fees = frappe.get_all(
		"Fees", filters={"student": name}, fields=["outstanding_amount"], ignore_permissions=True
	)

	results = frappe.get_all(
		"Assessment Result",
		filters={"student": name},
		fields=["name", "course", "total_score", "maximum_score", "grade"],
		order_by="creation desc",
		limit_page_length=5,
		ignore_permissions=True,
	)

	return {
		"name": doc.name,
		"student_name": doc.student_name,
		"first_name": doc.first_name,
		"last_name": doc.last_name or "",
		"gender": doc.gender or "",
		"date_of_birth": str(doc.date_of_birth or ""),
		"blood_group": doc.blood_group or "",
		"nationality": doc.nationality or "",
		"student_email_id": doc.student_email_id or "",
		"student_mobile_number": doc.student_mobile_number or "",
		"joining_date": str(doc.joining_date or ""),
		"enabled": bool(doc.enabled),
		"image": doc.image or None,
		"address": ", ".join(
			p for p in [doc.address_line_1, doc.address_line_2, doc.city, doc.state, doc.country, doc.pincode] if p
		),
		"program": program,
		"student_group": group,
		"guardians": guardians,
		"attendance": {
			"present": attendance_counts["Present"],
			"absent": attendance_counts["Absent"],
			"leave": attendance_counts["Leave"],
			"marked": marked,
			"percent": round(attendance_counts["Present"] / marked * 100, 1) if marked else None,
		},
		"fees": {
			"invoice_count": len(fees),
			"outstanding_total": sum(f.outstanding_amount or 0 for f in fees),
		},
		"recent_results": results,
	}
