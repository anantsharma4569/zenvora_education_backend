"""One-off demo data seeder for a fresh, empty Zenvora Education database.

NOT wired into hooks.py or the patch system - run manually, once, via:

    bench --site school.localhost execute zenvora_education.seed_demo_data.run

Refuses to run if a Company already exists, since it is not idempotent and
was written to populate a database that was just wiped clean, not to be
re-run against live data.

The only accounting simplification here: fee "collection" is faked by
setting Fees.outstanding_amount directly instead of posting real Payment
Entries/GL entries, since this script exists to back dashboard numbers, not
to stand up a real accounting trail. Nothing else takes a shortcut - every
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

GROUPS = [
	# (program_name, group_label, target_attendance_pct, student_count)
	("Grade 6", "Grade 6 - A", 96, 15),
	("Grade 7", "Grade 7 - B", 93, 14),
	("Grade 8", "Grade 8 - A", 90, 13),
	("Grade 9", "Grade 9 - A", 88, 13),
	("Grade 9", "Grade 9 - B", 82, 12),
	("Grade 10", "Grade 10 - A", 79, 12),
	("Grade 11", "Grade 11 - Science", 94, 11),
]

PROGRAM_FEE = {
	"Grade 6": 16000,
	"Grade 7": 17000,
	"Grade 8": 18000,
	"Grade 9": 19000,
	"Grade 10": 20000,
	"Grade 11": 21000,
}

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
	"Meera", "Pooja", "Rahul", "Sanjay", "Neha", "Priya",
]
LAST_NAMES = [
	"Sharma", "Verma", "Gupta", "Kumar", "Singh", "Patel", "Reddy", "Nair",
	"Iyer", "Rao", "Mehta", "Joshi", "Desai", "Kapoor", "Malhotra",
]

random.seed(42)
_used_names = set()


def _unique_name():
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
	frappe.flags.in_import = True
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

	print("Creating Programs...")
	programs = {}
	for program_name in PROGRAM_FEE:
		programs[program_name] = create_program(program_name, department)
	print(f"  {list(programs.values())}")

	print("Creating Fee Category and Fee Structures...")
	fee_category = create_fee_category("Tuition Fee")
	fee_structures = {}
	for program_name, amount in PROGRAM_FEE.items():
		fee_structures[program_name] = create_fee_structure(
			programs[program_name],
			academic_year,
			[{"fees_category": fee_category, "amount": amount}],
			academic_term=term_2,
		)
	print(f"  {fee_structures}")

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

	print("Creating instructors (one per Student Group) and extra staff...")
	instructors_by_group = {}
	employees = []
	for _, group_label, _, _ in GROUPS:
		fname, lname = _unique_name()
		result = create_employee(
			first_name=fname,
			last_name=lname,
			gender=random.choice(["Male", "Female"]),
			date_of_birth=f"{random.randint(1978, 1995)}-0{random.randint(1, 9)}-1{random.randint(0, 8)}",
			department=department,
			designation=designations["Teacher"],
			date_of_joining=f"{random.randint(2019, 2025)}-0{random.randint(1, 6)}-01",
			company=company_name,
			personal_email=f"{fname.lower()}.{lname.lower()}{random.randint(100, 999)}@zenvora-staff.example",
			is_instructor=1,
		)
		employees.append(result["employee"])
		instructors_by_group[group_label] = result["instructor"]

	for d_name in ("Accountant", "Accountant", "Front Desk Executive"):
		fname, lname = _unique_name()
		result = create_employee(
			first_name=fname,
			last_name=lname,
			gender=random.choice(["Male", "Female"]),
			date_of_birth=f"{random.randint(1978, 1995)}-0{random.randint(1, 9)}-1{random.randint(0, 8)}",
			department=department,
			designation=designations[d_name],
			date_of_joining=f"{random.randint(2019, 2025)}-0{random.randint(1, 6)}-01",
			company=company_name,
			personal_email=f"{fname.lower()}.{lname.lower()}{random.randint(100, 999)}@zenvora-staff.example",
			is_instructor=0,
		)
		employees.append(result["employee"])
	print(f"  {len(employees)} employees, {len(instructors_by_group)} instructors")

	school_days = _school_days_ending_today(14)
	print(f"Attendance window: {school_days[0]} .. {school_days[-1]}")

	print("Creating Student Groups, enrolling students, marking attendance and results...")
	total_students = 0
	all_results_summary = {"A+": 0, "A": 0, "B": 0, "C": 0, "D": 0, "F": 0}

	for program_name, group_label, target_pct, count in GROUPS:
		group_name = create_student_group(group_label, programs[program_name], academic_year, term_2)

		group_doc = frappe.get_doc("Student Group", group_name)
		group_doc.append(
			"instructors", {"instructor": instructors_by_group[group_label]}
		)

		fee_structure = fee_structures[program_name]
		fee_structure_doc = frappe.get_doc("Fee Structure", fee_structure)
		fee_amount = PROGRAM_FEE[program_name]

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
			# setup resets frappe.flags to its frappe.init() defaults (in_import back
			# to False) partway through this script, so setting it once up front
			# isn't reliable.
			frappe.flags.in_import = True
			created = create_student(
				first_name=fname,
				last_name=lname,
				student_email_id=email,
				program=programs[program_name],
				academic_year=academic_year,
				date_of_birth="2012-06-15",
				gender=random.choice(["Male", "Female"]),
			)
			student_names.append(created["student"])
			group_doc.append("students", {"student": created["student"], "active": 1})

		group_doc.insert(ignore_permissions=True) if group_doc.is_new() else group_doc.save(
			ignore_permissions=True
		)
		total_students += count

		# Attendance for the last 14 school days, hitting roughly target_pct present.
		for student in student_names:
			for day in school_days:
				status = "Present" if random.random() * 100 < target_pct else "Absent"
				frappe.get_doc(
					{
						"doctype": "Student Attendance",
						"student": student,
						"student_group": group_name,
						"date": day,
						"status": status,
					}
				).insert(ignore_permissions=True)

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

		print(f"  {group_label}: {count} students, target {target_pct}% attendance")

	print("Marking today's staff attendance...")
	for i, employee in enumerate(employees):
		if i < 7:
			status = "Present"
		elif i == 7:
			try:
				frappe.get_doc(
					{
						"doctype": "Attendance",
						"employee": employee,
						"status": "On Leave",
						"attendance_date": today(),
						"company": company_name,
					}
				).insert(ignore_permissions=True)
				continue
			except Exception:
				status = "Present"
		elif i == 8:
			status = "Absent"
		else:
			continue  # leave unmarked

		frappe.get_doc(
			{
				"doctype": "Attendance",
				"employee": employee,
				"status": status,
				"attendance_date": today(),
				"company": company_name,
			}
		).insert(ignore_permissions=True)

	print(f"Done. {total_students} students across {len(GROUPS)} groups.")
	print(f"Grade distribution: {all_results_summary}")
