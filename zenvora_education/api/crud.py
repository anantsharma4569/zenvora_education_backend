"""Edit / delete for every list page: get_record, update_record, delete_records.

One strict allowlist (RESOURCES) instead of a generic doctype endpoint: a
resource key maps to a fixed doctype and a fixed set of editable fields, so
the frontend can never touch anything that is not listed here. Admin-only.

Delete rules:
- Config records (department, program, section, ...) are really deleted, but
  Frappe refuses if anything still links to them - that refusal is returned
  per record as a readable reason instead of being forced through.
- Students and staff are *disabled*, not deleted: they carry logins, fees and
  attendance history that a hard delete would orphan.
"""

import frappe
from frappe import _
from frappe.utils import strip_html

from zenvora_education.api.utils import is_admin


def _abbr(company):
	return frappe.db.get_value("Company", company, "abbr")


# Each resource: doctype, editable `fields`, optional `rename` (callable doc ->
# new document name, used when a field that defines the document's name is
# edited - frappe.rename_doc also repoints every link to the old name),
# optional child table, and how a "delete" behaves.
RESOURCES = {
	"department": {
		"name_field": "department_name",
		"doctype": "Department",
		"fields": ["department_name"],
		"rename": lambda d: f"{d.department_name} - {_abbr(d.company)}",
	},
	"academic_year": {
		"name_field": "academic_year_name",
		"doctype": "Academic Year",
		"fields": ["academic_year_name", "year_start_date", "year_end_date"],
		"rename": lambda d: d.academic_year_name,
	},
	"academic_term": {
		"name_field": "term_name",
		"doctype": "Academic Term",
		"fields": ["term_name", "term_start_date", "term_end_date"],
		"rename": lambda d: f"{d.academic_year} ({d.term_name})",
	},
	"program": {
		"name_field": "program_name",
		"doctype": "Program",
		"fields": ["program_name", "department"],
		"rename": lambda d: d.program_name,
	},
	"student_group": {
		"name_field": "student_group_name",
		"doctype": "Student Group",
		"fields": ["student_group_name", "academic_term", "max_strength", "disabled"],
		"rename": lambda d: d.student_group_name,
	},
	"fee_category": {
		"name_field": "category_name",
		"doctype": "Fee Category",
		"fields": ["category_name"],
		"rename": lambda d: d.category_name,
		# Education creates an Item named after the category and looks it up by
		# that name in on_update, but never renames it - so it must move with it.
		"rename_also": ["Item"],
	},
	"fee_structure": {
		"doctype": "Fee Structure",
		"fields": ["academic_term"],
		"children": {"components": ["fees_category", "amount"]},
	},
	"course": {
		"name_field": "course_name",
		"doctype": "Course",
		"fields": ["course_name", "department", "description"],
		"rename": lambda d: d.course_name,
	},
	"course_schedule": {
		"doctype": "Course Schedule",
		"fields": [
			"student_group",
			"course",
			"instructor",
			"room",
			"schedule_date",
			"from_time",
			"to_time",
			"class_schedule_color",
		],
	},
	"student": {
		"doctype": "Student",
		"fields": ["first_name", "last_name", "date_of_birth", "gender"],
		"disable": {"enabled": 0},
	},
	"employee": {
		"doctype": "Employee",
		"fields": [
			"first_name",
			"last_name",
			"gender",
			"date_of_birth",
			"department",
			"designation",
			"date_of_joining",
			"personal_email",
		],
		"disable": {"status": "Inactive"},
		# The login is keyed by this email - changing it here would silently
		# desynchronise the two, so it is frozen once a login exists.
		"frozen_when_set": {"personal_email": "user_id"},
	},
}

INT_FIELDS = {"max_strength", "disabled"}
FLOAT_CHILD_FIELDS = {"amount"}


def _child_value(field, value):
	if field in FLOAT_CHILD_FIELDS:
		return float(value) if value not in (None, "") else 0
	return value


def _spec(resource):
	if not is_admin():
		frappe.throw(_("Not authorized"))
	spec = RESOURCES.get(resource)
	if not spec:
		frappe.throw(_("Unknown resource {0}").format(resource))
	return spec


@frappe.whitelist()
def get_record(resource, name):
	"""Editable fields of one record, to pre-fill the Edit form."""
	spec = _spec(resource)
	doc = frappe.get_doc(spec["doctype"], name)
	out = {"name": doc.name}
	for field in spec["fields"]:
		value = doc.get(field)
		out[field] = "" if value is None else str(value)
	for table, cols in spec.get("children", {}).items():
		out[table] = [{c: str(row.get(c) if row.get(c) is not None else "") for c in cols} for row in doc.get(table)]
	return out


@frappe.whitelist()
def update_record(resource, name, values):
	"""Update the allowlisted fields of one record. Returns its (possibly new) name."""
	spec = _spec(resource)
	if isinstance(values, str):
		values = frappe.parse_json(values)

	doctype = spec["doctype"]
	doc = frappe.get_doc(doctype, name)

	# A field that defines the document's name is ignored by a plain save (the
	# name is fixed at creation), so it has to go through rename_doc first -
	# which also repoints every link to the old name (students -> section, etc.).
	name_field = spec.get("name_field")
	if name_field and name_field in values and values[name_field] != doc.get(name_field):
		new_value = values[name_field]
		if not new_value:
			frappe.throw(_("{0} cannot be empty").format(doc.meta.get_label(name_field)))
		doc.set(name_field, new_value)
		target = spec["rename"](doc)
		if target != name:
			for linked in spec.get("rename_also", []):
				if frappe.db.exists(linked, name):
					frappe.rename_doc(linked, name, target, force=True)
					if linked == "Item":
						frappe.db.set_value("Item", target, "item_name", new_value)
			name = frappe.rename_doc(doctype, name, target, force=True)
			if "Item" in spec.get("rename_also", []):
				frappe.db.set_value(doctype, name, "item", name)
		frappe.db.set_value(doctype, name, name_field, new_value)
		doc = frappe.get_doc(doctype, name)

	for field in spec["fields"]:
		if field == name_field or field not in values:
			continue
		value = values[field]
		guard = spec.get("frozen_when_set", {}).get(field)
		if guard and doc.get(guard) and (value or None) != doc.get(field):
			frappe.throw(_("{0} cannot be changed because this person already has a login").format(doc.meta.get_label(field)))
		if field in INT_FIELDS:
			value = int(value) if value not in (None, "") else 0
		elif value == "":
			value = None
		doc.set(field, value)

	for table, cols in spec.get("children", {}).items():
		if table in values:
			doc.set(table, [{c: _child_value(c, row.get(c)) for c in cols} for row in values[table]])

	doc.save(ignore_permissions=True)
	return doc.name


@frappe.whitelist()
def delete_records(resource, names):
	"""Delete (or disable) each record; never raises for one bad record.

	Returns [{"name", "ok", "message"}] so the UI can show which ones were
	blocked and why.
	"""
	spec = _spec(resource)
	if isinstance(names, str):
		names = frappe.parse_json(names)

	results = []
	for name in names:
		frappe.db.savepoint("delete_one")
		try:
			if "disable" in spec:
				for field, value in spec["disable"].items():
					frappe.db.set_value(spec["doctype"], name, field, value)
				if resource == "student":
					# Education rejects any save of a section that still lists an inactive
					# student as active - which would block adding *anyone* to that section.
					frappe.db.set_value("Student Group Student", {"student": name}, "active", 0)
				message = _("Disabled (history kept)")
			else:
				frappe.delete_doc(spec["doctype"], name, ignore_permissions=True)
				message = ""
			results.append({"name": name, "ok": True, "message": message})
		except frappe.LinkExistsError as e:
			frappe.db.rollback(save_point="delete_one")
			results.append({"name": name, "ok": False, "message": _("In use, cannot delete: ") + _short(str(e))})
		except Exception as e:
			frappe.db.rollback(save_point="delete_one")
			results.append({"name": name, "ok": False, "message": _("Cannot delete: ") + _short(str(e))})
	frappe.db.commit()
	return results


def _short(message):
	text = strip_html(message or "").strip()
	return text if len(text) <= 260 else text[:257] + "..."
