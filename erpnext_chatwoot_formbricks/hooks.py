"""Frappe hooks for ERPNext Chatwoot Formbricks Integration."""

from . import __version__ as app_version

app_name = "erpnext_chatwoot_formbricks"
app_title = "ERPNext Chatwoot Formbricks"
app_publisher = "Your Name"
app_description = "Bidirectional integration with Chatwoot and Formbricks for ERPNext"
app_icon = "octicon octicon-comment-discussion"
app_color = "#3498db"
app_email = "your@email.com"
app_license = "MIT"
required_apps = ["frappe/erpnext"]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
app_include_js = "/assets/erpnext_chatwoot_formbricks/js/erpnext_chatwoot_formbricks.js"

# include js in doctype views
doctype_js = {
	"Customer": "public/js/customer.js",
	"Lead": "public/js/lead.js",
}

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	"Customer": {
		"after_insert": "erpnext_chatwoot_formbricks.common.contact_sync.sync_customer_to_chatwoot",
		"on_update": "erpnext_chatwoot_formbricks.common.contact_sync.sync_customer_to_chatwoot",
	},
	"Lead": {
		"after_insert": "erpnext_chatwoot_formbricks.common.contact_sync.sync_lead_to_chatwoot",
		"on_update": "erpnext_chatwoot_formbricks.common.contact_sync.sync_lead_to_chatwoot",
	},
	"Comment": {
		"after_insert": "erpnext_chatwoot_formbricks.chatwoot.issue_sync.send_comment_to_chatwoot",
	},
}

# Scheduled Tasks
# ---------------

scheduler_events = {
	"hourly": [
		"erpnext_chatwoot_formbricks.chatwoot.contact.sync_contacts_from_chatwoot",
		"erpnext_chatwoot_formbricks.formbricks.api.sync_surveys",
	],
	"daily": [
		"erpnext_chatwoot_formbricks.chatwoot.conversation.cleanup_old_conversations",
	],
}

# Jinja
# ----------

# Fixtures
# --------

fixtures = []

# Installing
# ----------

# before_install = "erpnext_chatwoot_formbricks.install.before_install"
after_install = "erpnext_chatwoot_formbricks.install.after_install"

# Uninstalling
# ------------

before_uninstall = "erpnext_chatwoot_formbricks.uninstall.before_uninstall"

# User Data Protection
# --------------------

user_data_fields = []

# Authentication and authorization
# --------------------------------

# auth_hooks = []

# Desk Notifications
# ------------------

# notification_config = "erpnext_chatwoot_formbricks.notifications.get_notification_config"

# Permissions
# -----------

# permission_query_conditions = {}
# has_permission = {}

# DocType Class
# ---------------

# override_doctype_class = {}

# Overriding Methods
# ------------------------------

# override_whitelisted_methods = {}

# Website
# -------

# website_route_rules = []

# Log clearing
# ------------

default_log_clearing_doctypes = {
	"Chatwoot Conversation": 90,
	"Formbricks Response": 365,
}
