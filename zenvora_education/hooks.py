app_name = "zenvora_education"
app_title = "Zenvora Education"
app_publisher = "Zenvora"
app_description = "Zenvora Education - custom School Management customizations for ERPNext/Education"
app_email = "sharmaanant171@gmail.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "zenvora_education",
# 		"logo": "/assets/zenvora_education/logo.png",
# 		"title": "Zenvora Education",
# 		"route": "/zenvora_education",
# 		"has_permission": "zenvora_education.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/zenvora_education/css/zenvora_education.css"
# app_include_js = "/assets/zenvora_education/js/zenvora_education.js"

# include js, css files in header of web template
# web_include_css = "/assets/zenvora_education/css/zenvora_education.css"
# web_include_js = "/assets/zenvora_education/js/zenvora_education.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "zenvora_education/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "zenvora_education/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "zenvora_education.utils.jinja_methods",
# 	"filters": "zenvora_education.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "zenvora_education.install.before_install"
# after_install = "zenvora_education.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "zenvora_education.uninstall.before_uninstall"
# after_uninstall = "zenvora_education.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "zenvora_education.utils.before_app_install"
# after_app_install = "zenvora_education.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "zenvora_education.utils.before_app_uninstall"
# after_app_uninstall = "zenvora_education.utils.after_app_uninstall"

# Build
# ------------------
# To hook into the build process

# after_build = "zenvora_education.build.after_build"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "zenvora_education.notifications.get_notification_config"

# Awesome Bar
# -----------
# Extra search results: list of dicts with label, description, route, index.
# route: ["List", "ToDo"], "/desk/docs/some/page", or "https://example.com"
# awesomebar_search = ["zenvora_education.search.awesomebar_results"]

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Fixtures
# --------
# Custom Fields this app adds to doctypes it doesn't own (never edit those
# doctypes' own JSON directly - see the "no core app edits" project rule).

fixtures = [
	{"dt": "Custom Field", "filters": [["name", "=", "Designation-is_teaching_role"]]},
]

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	"Instructor": {
		"validate": "zenvora_education.api.staff.warn_if_not_teaching_designation",
	}
}

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"zenvora_education.tasks.all"
# 	],
# 	"daily": [
# 		"zenvora_education.tasks.daily"
# 	],
# 	"hourly": [
# 		"zenvora_education.tasks.hourly"
# 	],
# 	"weekly": [
# 		"zenvora_education.tasks.weekly"
# 	],
# 	"monthly": [
# 		"zenvora_education.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "zenvora_education.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "zenvora_education.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "zenvora_education.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "zenvora_education.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["zenvora_education.utils.before_request"]
# after_request = ["zenvora_education.utils.after_request"]

# Job Events
# ----------
# before_job = ["zenvora_education.utils.before_job"]
# after_job = ["zenvora_education.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"zenvora_education.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []

