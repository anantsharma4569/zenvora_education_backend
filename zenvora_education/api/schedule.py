"""Course Schedule (timetable) for the Settings > Academics screen. Admin only.

Single records follow Frappe's own Course Schedule form (section, course, instructor, room, date,
from/to time, colour) and its validations (date inside the term, no clash for the section,
instructor or room). Edit/delete go through api.crud like every other list page.
"""

import calendar

import frappe
from frappe import _
from frappe.utils import add_days, getdate, strip_html

from zenvora_education.api.utils import is_admin

MAX_BULK_DAYS = 400
WEEKDAYS = list(calendar.day_name)


def _require_admin():
	if not is_admin():
		frappe.throw(_("Not authorized"))


@frappe.whitelist()
def list_instructors():
	_require_admin()
	return frappe.get_all(
		"Instructor",
		filters={"status": "Active"},
		fields=["name", "instructor_name"],
		order_by="instructor_name",
		ignore_permissions=True,
	)


@frappe.whitelist()
def list_rooms():
	_require_admin()
	return frappe.get_all(
		"Room", fields=["name", "room_name", "room_number", "seating_capacity"], order_by="name", ignore_permissions=True
	)


@frappe.whitelist()
def list_course_schedules():
	_require_admin()
	rows = frappe.get_all(
		"Course Schedule",
		fields=[
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
		],
		order_by="schedule_date desc, from_time asc",
		ignore_permissions=True,
	)
	for row in rows:
		row["schedule_date"] = str(row.schedule_date) if row.schedule_date else ""
		row["from_time"] = str(row.from_time or "")
		row["to_time"] = str(row.to_time or "")
	return rows


@frappe.whitelist()
def create_course_schedule(
	student_group, course, instructor, room, schedule_date, from_time, to_time, class_schedule_color=None
):
	_require_admin()
	doc = frappe.get_doc(
		{
			"doctype": "Course Schedule",
			"student_group": student_group,
			"course": course,
			"instructor": instructor,
			"room": room,
			"schedule_date": schedule_date,
			"from_time": from_time,
			"to_time": to_time,
			"class_schedule_color": class_schedule_color or None,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


@frappe.whitelist()
def create_course_schedules_bulk(
	student_group, course, instructor, room, from_time, to_time, start_date, end_date, days, class_schedule_color=None
):
	"""Frappe's Course Scheduling Tool: one Course Schedule per chosen weekday between two dates
	(both ends included). Days that clash or fall outside the term are skipped and reported,
	the rest are still created."""
	_require_admin()
	if isinstance(days, str):
		days = frappe.parse_json(days)
	days = [d for d in days if d in WEEKDAYS]
	if not days:
		frappe.throw(_("Please select at least one day to schedule the course."))

	start, end = getdate(start_date), getdate(end_date)
	if start > end:
		frappe.throw(_("Course Start Date cannot be greater than Course End Date."))
	if (end - start).days > MAX_BULK_DAYS:
		frappe.throw(_("Choose a range of at most {0} days.").format(MAX_BULK_DAYS))

	created, skipped = 0, []
	date = start
	while date <= end:
		if calendar.day_name[date.weekday()] in days:
			frappe.db.savepoint("bulk_schedule")
			try:
				create_course_schedule(
					student_group, course, instructor, room, str(date), from_time, to_time, class_schedule_color
				)
				created += 1
			except Exception as e:
				frappe.db.rollback(save_point="bulk_schedule")
				frappe.clear_messages()
				skipped.append({"date": str(date), "reason": _short(str(e))})
		date = add_days(date, 1)
	frappe.db.commit()
	return {"created": created, "skipped": skipped}


def _short(message):
	text = strip_html(message or "").strip()
	return text if len(text) <= 160 else text[:157] + "..."
