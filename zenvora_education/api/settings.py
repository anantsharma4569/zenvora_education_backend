import frappe
from frappe import _

from zenvora_education.api.utils import as_administrator, is_admin


def _require_admin():
	if not is_admin():
		frappe.throw(_("Not authorized"))


def _default_company():
	return frappe.get_all("Company", limit_page_length=1, pluck="name", ignore_permissions=True)[0]


# --- Company (created via the Frappe desk during ERPNext setup, read-only here) ---


@frappe.whitelist()
def list_companies():
	_require_admin()
	return frappe.get_all(
		"Company", fields=["name", "default_currency", "country"], order_by="name", ignore_permissions=True
	)


# --- Department ---


@frappe.whitelist()
def list_departments():
	_require_admin()
	return frappe.get_all(
		"Department",
		fields=["name", "department_name", "company"],
		order_by="department_name",
		ignore_permissions=True,
	)


@frappe.whitelist()
def create_department(department_name, company=None):
	_require_admin()
	doc = frappe.get_doc(
		{
			"doctype": "Department",
			"department_name": department_name,
			"company": company or _default_company(),
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


# --- Academic Year ---


@frappe.whitelist()
def list_academic_years():
	_require_admin()
	return frappe.get_all(
		"Academic Year",
		fields=["name", "year_start_date", "year_end_date"],
		order_by="year_start_date desc",
		ignore_permissions=True,
	)


@frappe.whitelist()
def create_academic_year(academic_year_name, year_start_date, year_end_date):
	_require_admin()
	doc = frappe.get_doc(
		{
			"doctype": "Academic Year",
			"academic_year_name": academic_year_name,
			"year_start_date": year_start_date,
			"year_end_date": year_end_date,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


# --- Academic Term ---


@frappe.whitelist()
def list_academic_terms(academic_year=None):
	_require_admin()
	filters = {}
	if academic_year:
		filters["academic_year"] = academic_year
	return frappe.get_all(
		"Academic Term",
		filters=filters,
		fields=["name", "academic_year", "term_name", "term_start_date", "term_end_date"],
		order_by="term_start_date",
		ignore_permissions=True,
	)


@frappe.whitelist()
def create_academic_term(academic_year, term_name, term_start_date, term_end_date):
	_require_admin()
	doc = frappe.get_doc(
		{
			"doctype": "Academic Term",
			"academic_year": academic_year,
			"term_name": term_name,
			"term_start_date": term_start_date,
			"term_end_date": term_end_date,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


# --- Program ---


@frappe.whitelist()
def list_programs():
	_require_admin()
	return frappe.get_all(
		"Program", fields=["name", "program_name", "department"], order_by="program_name", ignore_permissions=True
	)


@frappe.whitelist()
def create_program(program_name, department=None):
	_require_admin()
	doc = frappe.get_doc({"doctype": "Program", "program_name": program_name, "department": department})
	doc.insert(ignore_permissions=True)
	return doc.name


# --- Student Group (Class / Section) ---


@frappe.whitelist()
def list_student_groups():
	_require_admin()
	rows = frappe.get_all(
		"Student Group",
		fields=["name", "student_group_name", "program", "academic_year", "academic_term", "max_strength", "disabled"],
		order_by="student_group_name",
		ignore_permissions=True,
	)
	counts = dict(
		frappe.db.sql(
			"""select sgs.parent, count(*) from `tabStudent Group Student` sgs
			join `tabStudent` s on s.name = sgs.student and s.enabled = 1
			where sgs.active = 1 group by sgs.parent"""
		)
	)
	for row in rows:
		row["student_count"] = counts.get(row.name, 0)
	return rows


@frappe.whitelist()
def create_student_group(student_group_name, program, academic_year, academic_term=None, max_strength=0):
	_require_admin()
	doc = frappe.get_doc(
		{
			"doctype": "Student Group",
			"student_group_name": student_group_name,
			"group_based_on": "Batch",
			"program": program,
			"academic_year": academic_year,
			"academic_term": academic_term,
			"max_strength": max_strength,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


# --- Fee Category ---


@frappe.whitelist()
def list_fee_categories():
	_require_admin()
	return frappe.get_all(
		"Fee Category", fields=["name", "category_name"], order_by="category_name", ignore_permissions=True
	)


@frappe.whitelist()
def create_fee_category(category_name):
	_require_admin()

	# Fee Category auto-creates a sales Item (see education.../fee_category.py after_insert).
	# India Compliance requires an HSN/SAC code on sales items, and exposes exactly this
	# flag for cross-app item creation (see india_compliance/gst_india/overrides/item.py) -
	# 999231 is the standard GST SAC code for "Secondary education services, general".
	if frappe.db.exists("GST HSN Code", "999231"):
		frappe.flags.cross_app_hsn_code = "999231"

	doc = frappe.get_doc({"doctype": "Fee Category", "category_name": category_name})

	# Fee Category.after_insert creates a linked Item - that insert runs under
	# frappe.session.user regardless of the ignore_permissions passed here.
	with as_administrator():
		doc.insert(ignore_permissions=True)

	return doc.name


# --- Fee Structure ---


@frappe.whitelist()
def list_fee_structures():
	_require_admin()
	return frappe.get_all(
		"Fee Structure",
		fields=["name", "program", "academic_year", "academic_term", "total_amount"],
		order_by="creation desc",
		ignore_permissions=True,
	)


@frappe.whitelist()
def create_fee_structure(program, academic_year, components, academic_term=None):
	"""`components` is a list of {"fees_category": <Fee Category name>, "amount": <number>}.

	Receivable account/cost center/company are pulled from the school's Company
	defaults rather than asked for in the form - admins shouldn't need to know
	chart-of-accounts details just to set up a fee structure.
	"""
	_require_admin()
	if isinstance(components, str):
		components = frappe.parse_json(components)

	if not components:
		frappe.throw(_("At least one fee component is required"))

	company_name = _default_company()
	company = frappe.get_cached_doc("Company", company_name)

	doc = frappe.get_doc(
		{
			"doctype": "Fee Structure",
			"program": program,
			"academic_year": academic_year,
			"academic_term": academic_term,
			"company": company_name,
			"receivable_account": company.default_receivable_account,
			"cost_center": company.cost_center,
			"components": [{"fees_category": c["fees_category"], "amount": c["amount"]} for c in components],
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name
