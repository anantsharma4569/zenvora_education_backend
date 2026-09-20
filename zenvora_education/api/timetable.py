"""Timetable (read-only calendar) for the View Time Table screen.

Built on Course Schedule records. Access:
  admin    -> any section (get_timetable) plus the class/section pickers (get_timetable_options)
  teacher  -> only their own lessons (get_my_timetable), or a section they teach (get_timetable)
  student  -> only the sections they belong to (get_my_timetable)
"""

import frappe
from frappe import _
from frappe.utils import getdate

from zenvora_education.api.utils import (
	get_current_instructor,
	get_current_student,
	get_instructor_student_groups,
	get_student_groups_for_student,
	is_admin,
)

MAX_RANGE_DAYS = 400
FIELDS = [
	"name",
	"student_group",
	"program",
	"course",
	"instructor",
	"instructor_name",
	"room",
	"schedule_date",
	"from_time",
	"to_time",
	"class_schedule_color",
]


def _range(from_date, to_date):
	start, end = getdate(from_date), getdate(to_date)
	if start > end:
		frappe.throw(_("'From' date must be on or before the 'To' date."))
	if (end - start).days > MAX_RANGE_DAYS:
		frappe.throw(_("Choose a range of at most {0} days.").format(MAX_RANGE_DAYS))
	return start, end


def _rows(filters, start, end):
	filters = {**filters, "schedule_date": ["between", [start, end]]}
	rows = frappe.get_all(
		"Course Schedule",
		filters=filters,
		fields=FIELDS,
		order_by="schedule_date asc, from_time asc",
		ignore_permissions=True,
	)
	course_names = _lookup("Course", "course_name", {r.course for r in rows})
	room_names = _lookup("Room", "room_name", {r.room for r in rows})
	group_names = _lookup("Student Group", "student_group_name", {r.student_group for r in rows})
	return [
		{
			"name": r.name,
			"student_group": r.student_group,
			"student_group_name": group_names.get(r.student_group) or r.student_group,
			"program": r.program or "",
			"course": r.course,
			"course_name": course_names.get(r.course) or r.course,
			"instructor": r.instructor or "",
			"instructor_name": r.instructor_name or "",
			"room": r.room or "",
			"room_name": room_names.get(r.room) or r.room or "",
			"schedule_date": str(r.schedule_date),
			"from_time": str(r.from_time or ""),
			"to_time": str(r.to_time or ""),
			"color": r.class_schedule_color or "",
		}
		for r in rows
	]


def _lookup(doctype, field, names):
	names = [n for n in names if n]
	if not names:
		return {}
	return {
		d.name: d[field]
		for d in frappe.get_all(doctype, filters={"name": ["in", names]}, fields=["name", field], ignore_permissions=True)
	}


@frappe.whitelist()
def get_timetable_options():
	"""Admin only: classes (Programs) with their sections (Student Groups) for the two pickers."""
	if not is_admin():
		frappe.throw(_("Not authorized"))
	programs = frappe.get_all("Program", fields=["name", "program_name"], order_by="program_name", ignore_permissions=True)
	groups = frappe.get_all(
		"Student Group",
		filters={"disabled": 0},
		fields=["name", "student_group_name", "program"],
		order_by="student_group_name",
		ignore_permissions=True,
	)
	return {"programs": programs, "sections": groups}


@frappe.whitelist()
def get_timetable(student_group, from_date, to_date):
	"""Lessons of one section between two dates (both included)."""
	if not is_admin():
		instructor = get_current_instructor()
		student = get_current_student()
		if instructor:
			allowed = get_instructor_student_groups(instructor)
		elif student:
			allowed = get_student_groups_for_student(student)
		else:
			allowed = []
		if student_group not in allowed:
			frappe.throw(_("Not authorized"))
	start, end = _range(from_date, to_date)
	return _rows({"student_group": student_group}, start, end)


@frappe.whitelist()
def get_my_timetable(from_date, to_date):
	"""The logged-in teacher's lessons, or the logged-in student's sections' lessons."""
	start, end = _range(from_date, to_date)
	instructor = get_current_instructor()
	if instructor:
		return _rows({"instructor": instructor}, start, end)
	student = get_current_student()
	if student:
		groups = get_student_groups_for_student(student)
		return _rows({"student_group": ["in", groups]}, start, end) if groups else []
	frappe.throw(_("No instructor or student profile is linked to this user."))