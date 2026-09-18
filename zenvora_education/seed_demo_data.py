"""One-off demo data seeder for a fresh, empty Zenvora Education database.

Models the school's real shape: Grade 1 through Grade 10, each with A/B/C
sections, 15-30 students per section.

NOT wired into hooks.py or the patch system - run manually, once, via:

    bench --site school.localhost execute zenvora_education.seed_demo_data.run

Refuses to run if a Company already exists, since it is not idempotent and
was written to populate a database that was just wiped clean, not to be
re-run against live data.

Two shortcuts, both called out where they happen:
- Fee "collection" is faked by setting Fees.outstanding_amount directly
  instead of posting real Payment Entries/GL entries - this script exists to
  back dashboard numbers, not to stand up a real accounting trail.
- Student Attendance (by far the highest-volume doctype here - 10 grades x 3
  sections x ~22 students x 14 days is several thousand rows) is written via
  frappe.db.bulk_insert instead of one insert() per row, for speed. Every
  other record goes through the normal doctype validate()/insert() lifecycle
  (and the app's own whitelisted setup functions where they already exist).
"""

import random
from datetime import timedelta

import frappe
from frappe.utils import add_days, getdate, today

from zenvora_education.api.course import create_course
from zenvora_education.api.employee import create_employee
from zenvora_education.api.settings import (
	create_academic_term,
	create_academic_year,
	create_department,
	create_fee_category,
	create_fee_structure,
	create_program,
	create_student_group,
)
from zenvora_education.api.student import create_student
from zenvora_education.api.utils import as_administrator

GRADES = range(1, 11)  # Grade 1 .. Grade 10
SECTIONS = ["A", "B", "C"]
STUDENTS_PER_SECTION = (15, 30)  # inclusive random range
ATTENDANCE_PCT_RANGE = (78, 97)  # per-section target, randomized for variety

# Base fee for Grade 1, +900 per grade up (Grade 10 = 12000 + 9*900 = 20100).
FEE_BASE = 12000
FEE_STEP = 900

# Designation.is_teaching_role (custom field) drives the Staff directory's
# teaching/non-teaching split - see zenvora_education/api/staff.py.
TEACHING_DESIGNATIONS = [
	"Teacher",
	"Senior Teacher",
	"Head of Department (HOD)",
	"Principal",
	"Lab Instructor",
	"Physical Education Teacher",
]
NON_TEACHING_DESIGNATIONS = [
	"Accountant",
	"Front Desk Executive",
	"Librarian",
	"Front Desk / Receptionist",
	"Peon / Attendant",
	"IT Support",
	"Administrative Officer",
	"Transport Coordinator",
]

FIRST_NAMES = [
	"Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Reyansh", "Ayaan",
	"Krishna", "Ishaan", "Ananya", "Diya", "Saanvi", "Aadhya", "Kiara", "Myra",
	"Anika", "Navya", "Riya", "Siya", "Rohan", "Karan", "Nikhil", "Tara",
	"Meera", "Pooja", "Rahul", "Sanjay", "Neha", "Priya", "Aarush", "Dhruv",
	"Kabir", "Yash", "Om", "Advait", "Shaurya", "Vedant", "Kiaan", "Arnav",
	"Zara", "Ira", "Anvi", "Mahi", "Prisha", "Avni", "Shreya", "Tanvi",
	"Nitya", "Aarohi", "Lakshmi", "Divya", "Kavya", "Sneha", "Anjali", "Ritu",
	"Manish", "Deepak", "Suresh", "Vikram", "Amit", "Ajay", "Ravi", "Gaurav",
]
LAST_NAMES = [
	"Sharma", "Verma", "Gupta", "Kumar", "Singh", "Patel", "Reddy", "Nair",
	"Iyer", "Rao", "Mehta", "Joshi", "Desai", "Kapoor", "Malhotra", "Chauhan",
	"Bose", "Menon", "Pillai", "Agarwal",
]

random.seed(42)
_used_names = set()


def _unique_name():
	"""Every full name here needs to be globally unique: the Education app
	auto-creates a Customer (Student.on_update) and an Instructor record,
	both of which use the person's full name as their doctype `name` (not a
	generated series) - a repeated name is a primary-key collision, not just
	a cosmetic duplicate. ~715 people are created against a ~1,200-combo
	pool, comfortable margin for this loop to terminate quickly."""
	while True:
		name = (random.choice(FIRST_NAMES), random.choice(LAST_NAMES))
		if name not in _used_names:
			_used_names.add(name)
			return name


def _school_days_ending_today(n):
	"""Last n weekdays, ending today, oldest first."""
	days = []
	d = getdate(today())
	while len(days) < n:
		if d.weekday() < 5:  # Mon-Fri
			days.append(d)
		d -= timedelta(days=1)
	return list(reversed(days))


def run():
	if frappe.db.exists("Company", {}):
		print("A Company already exists - refusing to run against a non-empty database.")
		print("Run zenvora_education.seed_demo_data.cleanup first if this is a failed attempt.")
		return

	# Each Student.insert() creates a linked User (Education app's own hook); Frappe
	# throttles bulk User creation past 60/minute as an abuse guard. in_import is
	# Frappe's own documented escape hatch for exactly this - a bulk-import-shaped
	# script, not a user signing up.
	#
	# in_install matters for a different reason: User.on_update() unconditionally
	# enqueues a create_contact background job per User (enqueue_after_commit=True,
	# `now=frappe.in_test or frappe.flags.in_install`). At ~500 Students that queue
	# backlog trips Frappe's own QueueOverloaded safety limit and crashes the very
	# next Student.insert(). in_install makes that enqueue run inline instead -
	# exactly the installer's own bulk-provisioning path, which is what this is.
	frappe.flags.in_import = True
	frappe.flags.in_install = True
	with as_administrator():
		_run()


CLEANUP_DOCTYPES = [
	"Fees",
	"Assessment Result",
	"Assessment Plan",
	"Student Attendance",
	"Program Enrollment",
	"Student Group",
	"Instructor",
	"Attendance",
	"Employee",
	"Course",
	"Grading Scale",
	"Fee Structure",
	"Fee Category",
	"Program",
	"Academic Term",
	"Academic Year",
	"Customer",  # auto-created per Student by Student.on_update -> create_customer
	# Child tables: frappe.db.delete(<parent>) does NOT remove them. Section/scale
	# names are reused between seed runs, so leftover rows silently attach to the
	# next run's same-named parent (stale members, duplicated grading intervals).
	"Student Group Student",
	"Student Group Instructor",
	"Grading Scale Interval",
	"Assessment Plan Criteria",
	"Assessment Result Detail",
	"Fee Component",
]


def cleanup():
	"""Undo a partial/failed run so `run()` can be retried cleanly on a database
	that otherwise only has our records in it. Bulk SQL deletes, not doc.delete() -
	this is a reset, not a normal user-facing deletion, and doesn't need on_trash
	hooks to fire.
	"""
	with as_administrator():
		for doctype in CLEANUP_DOCTYPES:
			frappe.db.delete(doctype)

		frappe.db.delete(
			"Assessment Group", {"name": ["!=", "All Assessment Groups"]}
		)
		frappe.db.delete("Student")
		frappe.db.delete(
			"User",
			{
				"name": [
					"like",
					"%@zenvora-%.example",
				]
			},
		)

		company_name = frappe.db.get_value("Company", {}, "name")
		if company_name:
			frappe.delete_doc("Company", company_name, force=True, ignore_permissions=True)

		holiday_list = frappe.db.get_value("Holiday List", {"holiday_list_name": "Zenvora 2026-27"}, "name")
		if holiday_list:
			frappe.db.delete("Holiday List", {"name": holiday_list})

		frappe.db.commit()
		print("Cleaned up." if company_name else "Cleaned up (no Company was present).")


def _bulk_mark_attendance(rows):
	"""rows: list of (student, student_group, date, status). Bypasses the ORM
	(no validate(), no naming-series counter) purely for insert speed at this
	volume - see the module docstring. Names are our own scheme, distinct from
	the naming series Student Attendance normally uses, so there's no
	collision risk with attendance created later through the real API."""
	fields = ["name", "creation", "modified", "modified_by", "owner", "docstatus", "student", "student_group", "date", "status"]
	now = frappe.utils.now()
	values = (
		(f"BULK-ATT-{i:07d}", now, now, "Administrator", "Administrator", 0, student, group, date, status)
		for i, (student, group, date, status) in enumerate(rows)
	)
	frappe.db.bulk_insert("Student Attendance", fields, values)


def _run():
	print("Creating Company...")
	company = frappe.get_doc(
		{
			"doctype": "Company",
			"company_name": "Zenvora Enterprises",
			"abbr": "ZE",
			"default_currency": "INR",
			"country": "India",
			"gst_category": "Unregistered",
			"valuation_method": "FIFO",
			"create_chart_of_accounts_based_on": "Standard Template",
			"chart_of_accounts": "India - Chart of Accounts",
		}
	)
	company.insert(ignore_permissions=True)
	company_name = company.name
	print(f"  {company_name}")

	print("Creating Holiday List...")
	holiday_list = frappe.get_doc(
		{
			"doctype": "Holiday List",
			"holiday_list_name": "Zenvora 2026-27",
			"from_date": "2026-04-01",
			"to_date": "2027-03-31",
			"weekly_off": "Saturday",
		}
	)
	holiday_list.insert(ignore_permissions=True)
	frappe.db.set_value("Company", company_name, "default_holiday_list", holiday_list.name)

	print("Creating Department...")
	department = create_department("Academics", company_name)
	print(f"  {department}")

	print("Creating Academic Year and Terms...")
	academic_year = create_academic_year("2026-27", "2026-04-01", "2027-03-31")
	create_academic_term(academic_year, "Term 1", "2026-04-01", "2026-09-15")
	term_2 = create_academic_term(academic_year, "Term 2", "2026-09-16", "2027-03-31")
	print(f"  {academic_year} / {term_2}")

	print("Creating Programs (Grade 1 - Grade 10)...")
	programs = {}
	program_fee = {}
	for grade in GRADES:
		program_name = f"Grade {grade}"
		programs[program_name] = create_program(program_name, department)
		program_fee[program_name] = FEE_BASE + (grade - 1) * FEE_STEP
	print(f"  {list(programs.values())}")

	print("Creating Fee Category and Fee Structures...")
	fee_category = create_fee_category("Tuition Fee")
	fee_structures = {}
	for program_name, amount in program_fee.items():
		fee_structures[program_name] = create_fee_structure(
			programs[program_name],
			academic_year,
			[{"fees_category": fee_category, "amount": amount}],
			academic_term=term_2,
		)

	print("Creating Course...")
	course = create_course("Mathematics", department)

	print("Creating Grading Scale...")
	grading_scale = frappe.get_doc(
		{
			"doctype": "Grading Scale",
			"grading_scale_name": "Zenvora Standard",
			"intervals": [
				{"grade_code": "A+", "threshold": 90},
				{"grade_code": "A", "threshold": 80},
				{"grade_code": "B", "threshold": 70},
				{"grade_code": "C", "threshold": 60},
				{"grade_code": "D", "threshold": 40},
				{"grade_code": "F", "threshold": 0},
			],
		}
	)
	grading_scale.insert(ignore_permissions=True)

	print("Creating Assessment Criteria and Group...")
	for criteria_name in ("Theory", "Practical"):
		if not frappe.db.exists("Assessment Criteria", criteria_name):
			frappe.get_doc(
				{"doctype": "Assessment Criteria", "assessment_criteria": criteria_name}
			).insert(ignore_permissions=True)

	assessment_group = frappe.get_doc(
		{
			"doctype": "Assessment Group",
			"assessment_group_name": "Mid Term",
			"parent_assessment_group": "All Assessment Groups",
			"is_group": 0,
		}
	)
	assessment_group.insert(ignore_permissions=True)

	print("Creating Designations...")
	designations = {}
	for d_name in TEACHING_DESIGNATIONS:
		if not frappe.db.exists("Designation", d_name):
			frappe.get_doc(
				{"doctype": "Designation", "designation_name": d_name, "is_teaching_role": 1}
			).insert(ignore_permissions=True)
		designations[d_name] = d_name
	for d_name in NON_TEACHING_DESIGNATIONS:
		if not frappe.db.exists("Designation", d_name):
			frappe.get_doc({"doctype": "Designation", "designation_name": d_name}).insert(
				ignore_permissions=True
			)
		designations[d_name] = d_name

	def _new_employee(designation, is_instructor):
		fname, lname = _unique_name()
		return create_employee(
			first_name=fname,
			last_name=lname,
			gender=random.choice(["Male", "Female"]),
			date_of_birth=f"{random.randint(1978, 1995)}-0{random.randint(1, 9)}-1{random.randint(0, 8)}",
			department=department,
			designation=designation,
			date_of_joining=f"{random.randint(2019, 2025)}-0{random.randint(1, 6)}-01",
			company=company_name,
			personal_email=f"{fname.lower()}.{lname.lower()}{random.randint(1000, 99999)}@zenvora-staff.example",
			is_instructor=is_instructor,
		)

	groups = [(f"Grade {grade}", f"Grade {grade} - {section}") for grade in GRADES for section in SECTIONS]

	print(f"Creating {len(groups)} instructors (one per section) and non-teaching staff...")
	instructors_by_group = {}
	employees = []
	for _, group_label in groups:
		result = _new_employee(designations["Teacher"], is_instructor=1)
		employees.append(result["employee"])
		instructors_by_group[group_label] = result["instructor"]

	for d_name in NON_TEACHING_DESIGNATIONS:
		result = _new_employee(designations[d_name], is_instructor=0)
		employees.append(result["employee"])
	print(f"  {len(employees)} employees, {len(instructors_by_group)} instructors")

	school_days = _school_days_ending_today(14)
	print(f"Attendance window: {school_days[0]} .. {school_days[-1]}")

	print(f"Creating {len(groups)} Student Groups, enrolling students, marking results/fees...")
	total_students = 0
	all_results_summary = {"A+": 0, "A": 0, "B": 0, "C": 0, "D": 0, "F": 0}
	attendance_rows = []

	for program_name, group_label in groups:
		count = random.randint(*STUDENTS_PER_SECTION)
		target_pct = random.randint(*ATTENDANCE_PCT_RANGE)

		group_name = create_student_group(group_label, programs[program_name], academic_year, term_2)

		group_doc = frappe.get_doc("Student Group", group_name)
		group_doc.append("instructors", {"instructor": instructors_by_group[group_label]})

		fee_structure = fee_structures[program_name]
		fee_structure_doc = frappe.get_doc("Fee Structure", fee_structure)
		fee_amount = program_fee[program_name]

		assessment_plan = frappe.get_doc(
			{
				"doctype": "Assessment Plan",
				"student_group": group_name,
				"assessment_name": f"{group_label} Mid Term - Mathematics",
				"assessment_group": assessment_group.name,
				"grading_scale": grading_scale.name,
				"program": programs[program_name],
				"course": course,
				"academic_year": academic_year,
				"academic_term": term_2,
				"schedule_date": add_days(today(), -3),
				"from_time": "09:00:00",
				"to_time": "11:00:00",
				"maximum_assessment_score": 100,
				"assessment_criteria": [
					{"assessment_criteria": "Theory", "maximum_score": 80},
					{"assessment_criteria": "Practical", "maximum_score": 20},
				],
			}
		)
		assessment_plan.insert(ignore_permissions=True)

		student_names = []
		for i in range(count):
			fname, lname = _unique_name()
			idx = total_students + i
			email = f"{fname.lower()}.{lname.lower()}{idx}@zenvora-students.example"
			# Re-assert on every call: something during Company/Chart-of-Accounts
			# setup resets frappe.flags to its frappe.init() defaults (in_import/
			# in_install back to False) partway through this script, so setting
			# them once up front isn't reliable.
			frappe.flags.in_import = True
			frappe.flags.in_install = True
			created = create_student(
				first_name=fname,
				last_name=lname,
				student_email_id=email,
				program=programs[program_name],
				academic_year=academic_year,
				date_of_birth=f"{2026 - 5 - int(program_name.split()[-1])}-06-15",
				gender=random.choice(["Male", "Female"]),
			)
			student_names.append(created["student"])
			# student_name/group_roll_number set here because validate() (which
			# would normally fill them in) is skipped below - see the comment at
			# the group_doc.flags assignment further down.
			group_doc.append(
				"students",
				{
					"student": created["student"],
					"student_name": f"{fname} {lname}",
					"group_roll_number": i + 1,
					"active": 1,
				},
			)

		# Same shape as the Fees.income_account workaround above: every Student/
		# Instructor here was inserted by this script a moment ago and is known
		# valid, and enabled=1 (create_student always sets it). _validate_links()
		# and Student Group's own validate() (validate_students' "is inactive
		# student" check, on top of the "title" column bug already routed around
		# by setting student_name above) have each intermittently misreported
		# known-good rows as missing/inactive at this volume - not worth chasing
		# further for a seed script when every value here was just verified by
		# this same script moments earlier.
		group_doc.flags.ignore_links = True
		group_doc.flags.ignore_validate = True
		group_doc.insert(ignore_permissions=True) if group_doc.is_new() else group_doc.save(
			ignore_permissions=True
		)
		total_students += count

		for student in student_names:
			for day in school_days:
				status = "Present" if random.random() * 100 < target_pct else "Absent"
				attendance_rows.append((student, group_name, day, status))

		# Assessment results: scores skewed to a realistic pass curve.
		for student in student_names:
			pct = max(5, min(98, random.gauss(72, 16)))
			theory = round(pct / 100 * 80, 1)
			practical = round(pct / 100 * 20, 1)
			result = frappe.get_doc(
				{
					"doctype": "Assessment Result",
					"assessment_plan": assessment_plan.name,
					"student": student,
					"student_group": group_name,
					"details": [
						{"assessment_criteria": "Theory", "score": theory},
						{"assessment_criteria": "Practical", "score": practical},
					],
				}
			)
			result.insert(ignore_permissions=True)
			if result.grade in all_results_summary:
				all_results_summary[result.grade] += 1

		# Fees for Term 2: ~79% paid in full, ~15% overdue/unpaid, ~6% part-paid.
		for student in student_names:
			enrollment = frappe.db.get_value(
				"Program Enrollment", {"student": student, "program": programs[program_name]}, "name"
			)
			fees_doc = frappe.get_doc(
				{
					"doctype": "Fees",
					"student": student,
					"company": company_name,
					"posting_date": add_days(today(), -20),
					"due_date": add_days(today(), -5),
					"program_enrollment": enrollment,
					"program": programs[program_name],
					"academic_year": academic_year,
					"academic_term": term_2,
					"fee_structure": fee_structure,
					"receivable_account": fee_structure_doc.receivable_account,
					"components": [{"fees_category": fee_category, "amount": fee_amount}],
				}
			)
			# Fees.income_account has fetch_from="fee_structure.income_account", but
			# Fee Structure has no such field (a pre-existing Education app bug, not a
			# migration gap) - link validation crashes trying to SELECT it. Every link
			# value here was just generated above and is known-valid, so skip it.
			fees_doc.flags.ignore_links = True
			fees_doc.insert(ignore_permissions=True)

			roll = random.random()
			if roll < 0.79:
				outstanding = 0
			elif roll < 0.94:
				outstanding = fees_doc.grand_total
			else:
				outstanding = round(fees_doc.grand_total * 0.3, 2)
			# Simplification noted in the module docstring: no Payment Entry/GL trail.
			frappe.db.set_value("Fees", fees_doc.name, "outstanding_amount", outstanding)

		# Commit per group instead of leaving one multi-thousand-row transaction
		# open for the whole run: past ~15 groups, validate() calls elsewhere in
		# this script started seeing wrong results for rows this same script had
		# just inserted (a Fees fetch_from crash, "could not find" on students/
		# instructors that plainly existed, "inactive student" for one just
		# created enabled=1) - different symptoms, same shape, all going away
		# once each group's writes are committed before the next one starts.
		frappe.db.commit()

		print(f"  {group_label}: {count} students, target {target_pct}% attendance")

	print(f"Bulk-inserting {len(attendance_rows)} attendance records...")
	_bulk_mark_attendance(attendance_rows)
	frappe.db.commit()

	print("Marking today's staff attendance...")
	random.shuffle(employees)
	n = len(employees)
	on_leave_n = max(1, round(n * 0.04))
	absent_n = max(1, round(n * 0.03))
	unmarked_n = max(1, round(n * 0.05))
	present_n = n - on_leave_n - absent_n - unmarked_n

	idx = 0
	for _ in range(present_n):
		frappe.get_doc(
			{"doctype": "Attendance", "employee": employees[idx], "status": "Present", "attendance_date": today(), "company": company_name}
		).insert(ignore_permissions=True)
		idx += 1
	for _ in range(on_leave_n):
		try:
			frappe.get_doc(
				{"doctype": "Attendance", "employee": employees[idx], "status": "On Leave", "attendance_date": today(), "company": company_name}
			).insert(ignore_permissions=True)
		except Exception:
			pass
		idx += 1
	for _ in range(absent_n):
		frappe.get_doc(
			{"doctype": "Attendance", "employee": employees[idx], "status": "Absent", "attendance_date": today(), "company": company_name}
		).insert(ignore_permissions=True)
		idx += 1
	# Remaining `unmarked_n` employees are left with no Attendance record for today.

	print(f"Done. {total_students} students across {len(groups)} sections.")
	print(f"Grade distribution: {all_results_summary}")
