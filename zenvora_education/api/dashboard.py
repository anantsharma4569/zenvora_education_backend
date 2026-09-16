import frappe

from zenvora_education.api.utils import (
	get_current_instructor,
	get_current_student,
	get_instructor_student_groups,
	get_student_groups_for_student,
	is_accounts,
	is_admin,
)


@frappe.whitelist()
def get_dashboard():
	if is_admin():
		return _admin_dashboard()

	instructor = get_current_instructor()
	if instructor:
		return _teacher_dashboard(instructor)

	if is_accounts():
		return _accounts_dashboard()

	student = get_current_student()
	if student:
		return _student_dashboard(student)

	frappe.throw("No dashboard available for this user")


GRADE_ORDER = ["A+", "A", "B", "C", "D", "F"]


def _admin_dashboard():
	return {
		"role": "admin",
		"student_count": frappe.db.count("Student", {"enabled": 1}),
		"employee_count": frappe.db.count("Employee", {"status": "Active"}),
		"instructor_count": frappe.db.count("Instructor", {"status": "Active"}),
		"today_present": frappe.db.count(
			"Student Attendance", {"date": frappe.utils.today(), "status": "Present"}
		),
		"today_absent": frappe.db.count(
			"Student Attendance", {"date": frappe.utils.today(), "status": "Absent"}
		),
		"attendance_by_group": _attendance_by_group(),
		"attendance_trend": _attendance_trend(),
		"grade_distribution": _grade_distribution(),
		"fees_summary": _fees_summary(),
		"staff_today": _staff_today(),
		"exam_summary": _exam_summary(),
		"low_attendance_count": _low_attendance_count(),
	}


def _attendance_by_group():
	"""Today's present/marked rate for each Student Group, most-attended first."""
	groups = frappe.get_all(
		"Student Group", filters={"disabled": 0}, fields=["name", "student_group_name"]
	)
	result = []
	for group in groups:
		total = frappe.db.count(
			"Student Attendance", {"student_group": group.name, "date": frappe.utils.today()}
		)
		if not total:
			continue
		present = frappe.db.count(
			"Student Attendance",
			{"student_group": group.name, "date": frappe.utils.today(), "status": "Present"},
		)
		result.append(
			{"name": group.student_group_name, "pct": round(present / total * 100, 1)}
		)
	result.sort(key=lambda g: g["pct"], reverse=True)
	return result


def _attendance_trend():
	"""Overall school-wide attendance rate for each of the last 14 marked school days."""
	rows = frappe.db.sql(
		"""
		select
			`date`,
			sum(case when status = 'Present' then 1 else 0 end) as present,
			count(*) as total
		from `tabStudent Attendance`
		group by `date`
		order by `date` desc
		limit 14
		""",
		as_dict=True,
	)
	rows.reverse()
	return [
		{
			"date": str(row.date),
			"rate": round(row.present / row.total * 100, 1) if row.total else 0,
		}
		for row in rows
	]


def _grade_distribution():
	"""Count of Assessment Results per grade, in grade order, zero-filled."""
	counts = dict.fromkeys(GRADE_ORDER, 0)
	rows = frappe.db.sql(
		"select grade, count(name) as count from `tabAssessment Result` group by grade",
		as_dict=True,
	)
	for row in rows:
		if row.grade in counts:
			counts[row.grade] = row.count
	return [{"label": grade, "value": counts[grade]} for grade in GRADE_ORDER]


def _fees_summary():
	"""Billed/collected/outstanding across all Fees invoices, plus overdue detail."""
	totals = frappe.db.sql(
		"""
		select
			sum(grand_total) as billed,
			sum(grand_total - outstanding_amount) as collected,
			sum(outstanding_amount) as outstanding
		from `tabFees`
		""",
		as_dict=True,
	)[0]
	overdue = frappe.db.sql(
		"""
		select
			sum(outstanding_amount) as overdue_amount,
			count(distinct student) as unpaid_students
		from `tabFees`
		where outstanding_amount > 0 and due_date < %s
		""",
		(frappe.utils.today(),),
		as_dict=True,
	)[0]
	return {
		"billed": totals.billed or 0,
		"collected": totals.collected or 0,
		"outstanding": totals.outstanding or 0,
		"overdue": overdue.overdue_amount or 0,
		"unpaid_students": overdue.unpaid_students or 0,
	}


def _exam_summary():
	"""Pass rate/median/below-40 across all Assessment Results, plus how many
	Student Groups have a published result versus how many exist at all."""
	rows = frappe.db.sql(
		"select total_score, maximum_score, student_group from `tabAssessment Result`",
		as_dict=True,
	)
	total_groups = frappe.db.count("Student Group", {"disabled": 0})
	if not rows:
		return {
			"pass_rate": 0,
			"median_score": 0,
			"below_40": 0,
			"total_results": 0,
			"published_groups": 0,
			"total_groups": total_groups,
		}

	percentages = sorted(
		(row.total_score / row.maximum_score * 100) if row.maximum_score else 0 for row in rows
	)
	n = len(percentages)
	median = (
		percentages[n // 2]
		if n % 2
		else (percentages[n // 2 - 1] + percentages[n // 2]) / 2
	)
	below_40 = sum(1 for p in percentages if p < 40)
	return {
		"pass_rate": round((n - below_40) / n * 100, 1),
		"median_score": round(median, 1),
		"below_40": below_40,
		"total_results": n,
		"published_groups": len({row.student_group for row in rows}),
		"total_groups": total_groups,
	}


def _low_attendance_count(threshold=75):
	"""Count of students whose overall attendance rate (across all marked days)
	is below `threshold` percent."""
	rows = frappe.db.sql(
		"""
		select
			sum(case when status = 'Present' then 1 else 0 end) as present,
			count(*) as total
		from `tabStudent Attendance`
		group by student
		""",
		as_dict=True,
	)
	return sum(1 for row in rows if row.total and (row.present / row.total * 100) < threshold)


def _staff_today():
	"""Today's Employee attendance, split by status, with unmarked as the remainder."""
	today = frappe.utils.today()
	present = frappe.db.count("Attendance", {"attendance_date": today, "status": "Present"})
	on_leave = frappe.db.count("Attendance", {"attendance_date": today, "status": "On Leave"})
	absent = frappe.db.count("Attendance", {"attendance_date": today, "status": "Absent"})
	active = frappe.db.count("Employee", {"status": "Active"})
	return {
		"present": present,
		"on_leave": on_leave,
		"absent_unapproved": absent,
		"unmarked": max(0, active - present - on_leave - absent),
	}


def _accounts_dashboard():
	return {
		"role": "accounts",
		"student_count": frappe.db.count("Student", {"enabled": 1}),
	}


def _teacher_dashboard(instructor):
	groups = get_instructor_student_groups(instructor)
	return {
		"role": "teacher",
		"instructor": instructor,
		"student_groups": groups,
	}


def _student_dashboard(student):
	groups = get_student_groups_for_student(student)
	attendance_summary = frappe.db.sql(
		"select status, count(name) as count from `tabStudent Attendance` where student = %s group by status",
		(student,),
		as_dict=True,
	)
	return {
		"role": "student",
		"student": student,
		"student_groups": groups,
		"attendance_summary": attendance_summary,
	}
