"""Uninstallation hooks for ERPNext Chatwoot Formbricks."""

import frappe


def before_uninstall():
	"""Run before app uninstallation."""
	# Remove custom fields
	custom_fields_to_remove = [
		("Customer", "chatwoot_contact_id"),
		("Customer", "formbricks_contact_id"),
		("Lead", "chatwoot_contact_id"),
		("Lead", "chatwoot_conversation_id"),
		("Lead", "formbricks_contact_id"),
		("Lead", "formbricks_response_id"),
		("Issue", "chatwoot_conversation_id"),
	]

	for doctype, fieldname in custom_fields_to_remove:
		try:
			frappe.delete_doc(
				"Custom Field",
				f"{doctype}-{fieldname}",
				ignore_missing=True,
				force=True,
			)
		except Exception:
			pass

	frappe.msgprint("ERPNext Chatwoot Formbricks custom fields removed.")
