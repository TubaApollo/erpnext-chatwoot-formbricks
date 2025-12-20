"""Installation hooks for ERPNext Chatwoot Formbricks."""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def after_install():
	"""Run after app installation."""
	setup_custom_fields()
	frappe.msgprint("ERPNext Chatwoot Formbricks installed successfully!")


def setup_custom_fields():
	"""Create custom fields for integration."""
	custom_fields = {
		"Customer": [
			dict(
				fieldname="chatwoot_contact_id",
				label="Chatwoot Contact ID",
				fieldtype="Data",
				insert_after="customer_name",
				read_only=1,
				print_hide=1,
				translatable=0,
			),
			dict(
				fieldname="formbricks_contact_id",
				label="Formbricks Contact ID",
				fieldtype="Data",
				insert_after="chatwoot_contact_id",
				read_only=1,
				print_hide=1,
				translatable=0,
			),
		],
		"Lead": [
			dict(
				fieldname="chatwoot_contact_id",
				label="Chatwoot Contact ID",
				fieldtype="Data",
				insert_after="lead_name",
				read_only=1,
				print_hide=1,
				translatable=0,
			),
			dict(
				fieldname="chatwoot_conversation_id",
				label="Chatwoot Conversation ID",
				fieldtype="Data",
				insert_after="chatwoot_contact_id",
				read_only=1,
				print_hide=1,
				translatable=0,
			),
			dict(
				fieldname="formbricks_contact_id",
				label="Formbricks Contact ID",
				fieldtype="Data",
				insert_after="chatwoot_conversation_id",
				read_only=1,
				print_hide=1,
				translatable=0,
			),
			dict(
				fieldname="formbricks_response_id",
				label="Formbricks Response ID",
				fieldtype="Data",
				insert_after="formbricks_contact_id",
				read_only=1,
				print_hide=1,
				translatable=0,
			),
		],
		"Issue": [
			dict(
				fieldname="chatwoot_conversation_id",
				label="Chatwoot Conversation ID",
				fieldtype="Data",
				insert_after="subject",
				read_only=1,
				print_hide=1,
				translatable=0,
			),
		],
		"User": [
			dict(
				fieldname="chatwoot_section",
				label="Chatwoot Integration",
				fieldtype="Section Break",
				insert_after="simultaneous_sessions",
				collapsible=1,
			),
			dict(
				fieldname="chatwoot_api_token",
				label="Chatwoot API Token",
				fieldtype="Password",
				insert_after="chatwoot_section",
				description="Personal Chatwoot API token. Messages will appear under your Chatwoot agent name. Leave empty to use global token.",
			),
		],
	}

	create_custom_fields(custom_fields)
