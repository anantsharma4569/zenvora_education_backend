import frappe
from frappe import _

from zenvora_education.api.utils import get_current_student, is_accounts, is_admin

FEE_FIELDS = [
	"name",
	"student",
	"student_name",
	"program",
	"due_date",
	"posting_date",
	"grand_total",
	"outstanding_amount",
]


@frappe.whitelist()
def get_fees(student=None):
	"""Admin/Accounts: all fee invoices (optionally filtered by student). No one else."""
	if not (is_admin() or is_accounts()):
		frappe.throw(_("Not authorized to view fee records"))

	filters = {}
	if student:
		filters["student"] = student

	return frappe.get_all(
		"Fees",
		filters=filters,
		fields=FEE_FIELDS,
		order_by="due_date desc",
	)


@frappe.whitelist()
def get_my_fees():
	"""Student: own fee invoices only."""
	student = get_current_student()
	if not student:
		frappe.throw(_("No Student record linked to this user"))

	return frappe.get_all(
		"Fees",
		filters={"student": student},
		fields=FEE_FIELDS,
		order_by="due_date desc",
	)
