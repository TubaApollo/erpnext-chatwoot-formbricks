"""Common contact synchronization utilities."""

import frappe


def sync_customer_to_chatwoot(doc, method=None):
	"""Sync ERPNext Customer to Chatwoot.

	This is called via doc_events hook.

	Args:
		doc: Customer document
		method: Event method (after_insert, on_update)
	"""
	from erpnext_chatwoot_formbricks.chatwoot.contact import sync_customer_to_chatwoot as _sync
	_sync(doc, method)


def sync_lead_to_chatwoot(doc, method=None):
	"""Sync ERPNext Lead to Chatwoot.

	This is called via doc_events hook.

	Args:
		doc: Lead document
		method: Event method (after_insert, on_update)
	"""
	settings = frappe.get_single("Chatwoot Settings")
	if not settings.enabled:
		return

	# Skip if already has Chatwoot ID (was created from Chatwoot)
	if doc.chatwoot_contact_id:
		return

	try:
		from erpnext_chatwoot_formbricks.chatwoot.api import ChatwootAPI

		api = ChatwootAPI(settings)

		# Check if contact already exists by email
		if doc.email_id:
			existing = api.search_contacts(doc.email_id)
			contacts = existing.get("payload", [])
			if contacts:
				# Link to existing contact
				contact_id = str(contacts[0].get("id"))
				frappe.db.set_value("Lead", doc.name, "chatwoot_contact_id", contact_id)
				frappe.db.commit()
				return

		# Create new contact
		result = api.create_contact(
			name=doc.lead_name,
			email=doc.email_id,
			phone=doc.mobile_no,
			identifier=doc.name,
			custom_attributes={
				"erpnext_lead": doc.name,
				"lead_source": doc.source,
			}
		)

		if result:
			contact_id = str(result.get("payload", {}).get("contact", {}).get("id", ""))
			if contact_id:
				frappe.db.set_value("Lead", doc.name, "chatwoot_contact_id", contact_id)
				frappe.db.commit()

	except Exception as e:
		frappe.log_error(f"Error syncing Lead {doc.name} to Chatwoot: {e}")


def find_erpnext_contact_by_email(email):
	"""Find an ERPNext Customer or Lead by email.

	Args:
		email: Email address to search for

	Returns:
		Tuple of (doctype, name) or (None, None)
	"""
	if not email:
		return None, None

	# Check Customer first
	customer = frappe.db.get_value("Customer", {"email_id": email}, "name")
	if customer:
		return "Customer", customer

	# Then check Lead
	lead = frappe.db.get_value("Lead", {"email_id": email}, "name")
	if lead:
		return "Lead", lead

	return None, None


def find_erpnext_contact_by_phone(phone):
	"""Find an ERPNext Customer or Lead by phone.

	Args:
		phone: Phone number to search for

	Returns:
		Tuple of (doctype, name) or (None, None)
	"""
	if not phone:
		return None, None

	# Normalize phone number (remove common formatting)
	normalized = "".join(c for c in phone if c.isdigit())

	# Check Customer first
	customer = frappe.db.get_value("Customer", {"mobile_no": phone}, "name")
	if customer:
		return "Customer", customer

	# Then check Lead
	lead = frappe.db.get_value("Lead", {"mobile_no": phone}, "name")
	if lead:
		return "Lead", lead

	return None, None
