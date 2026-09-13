import frappe


@frappe.whitelist(allow_guest=True)
def get_session():
	"""Guest-safe session check used by the frontend to decide whether to show /login."""
	user = frappe.session.user
	return {
		"user": user,
		"authenticated": user != "Guest",
	}
