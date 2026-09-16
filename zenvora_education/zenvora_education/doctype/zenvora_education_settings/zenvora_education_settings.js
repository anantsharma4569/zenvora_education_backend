// Copyright (c) 2026, Zenvora and contributors
// For license information, please see license.txt

frappe.ui.form.on("Zenvora Education Settings", {
	run_seed_data(frm) {
		frappe.confirm(
			__(
				"This creates a Company, ~30 Student Groups, ~700 students, attendance, results and fees in the background. It only works on an empty database and can take 15-25 minutes. Continue?"
			),
			() => {
				frappe.call({
					method:
						"zenvora_education.zenvora_education.doctype.zenvora_education_settings.zenvora_education_settings.run_seed",
					freeze: true,
					freeze_message: __("Queuing seed job..."),
					callback: () => {
						frappe.show_alert({
							message: __("Seed job queued - refresh this page in a few minutes to check status."),
							indicator: "blue",
						});
						frm.reload_doc();
					},
				});
			}
		);
	},
});
