import frappe
from frappe.sessions import get_csrf_token


@frappe.whitelist(allow_guest=True)
def get_session():
	"""Guest-safe session check used by the frontend to decide whether to show /login."""
	user = frappe.session.user
	authenticated = user != "Guest"
	return {
		"user": user,
		"authenticated": authenticated,
		# Cookie sessions are shared across localhost ports, so a session that was also opened in the
		# Frappe desk already carries a CSRF token and rejects POSTs without it ("Invalid Request").
		"csrf_token": get_csrf_token() if authenticated else None,
	}
