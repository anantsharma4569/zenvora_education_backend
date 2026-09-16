# Copyright (c) 2026, Zenvora and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from zenvora_education.api.utils import is_admin


class ZenvoraEducationSettings(Document):
	pass


@frappe.whitelist()
def run_seed():
	"""Queue zenvora_education.seed_demo_data.run() as a background job - it
	seeds a Company, Programs/Student Groups, ~700 students, attendance,
	results and fees, which reliably takes well past any HTTP request
	timeout, so this can't run inline on the request that clicks the button.
	"""
	if not is_admin():
		frappe.throw(_("Not authorized to run the demo data seeder"))

	if frappe.db.exists("Company", {}):
		frappe.throw(
			_(
				"A Company already exists - the seeder refuses to run against a non-empty "
				"database. Run zenvora_education.seed_demo_data.cleanup via bench console first "
				"if you want to reseed."
			)
		)

	frappe.db.set_single_value("Zenvora Education Settings", "seed_status", "Queued...")
	frappe.enqueue(
		"zenvora_education.zenvora_education.doctype.zenvora_education_settings.zenvora_education_settings.run_seed_job",
		queue="long",
		timeout=3600,
		job_name="zenvora_education_seed_demo_data",
	)
	return "queued"


def run_seed_job():
	"""The actual background job body - enqueued by run_seed(), never called
	directly over HTTP. Runs as Administrator (the default for a queued job
	with no `user` kwarg), same as running the seeder from bench console."""
	from zenvora_education import seed_demo_data

	frappe.db.set_single_value("Zenvora Education Settings", "seed_status", "Running...")
	frappe.db.commit()
	try:
		seed_demo_data.run()
	except Exception:
		frappe.db.set_single_value(
			"Zenvora Education Settings", "seed_status", f"Failed: {frappe.get_traceback()[-1000:]}"
		)
		frappe.db.commit()
		raise
	else:
		frappe.db.set_single_value("Zenvora Education Settings", "seed_status", "Completed")
		frappe.db.set_single_value("Zenvora Education Settings", "last_seeded_on", frappe.utils.now())
		frappe.db.commit()
