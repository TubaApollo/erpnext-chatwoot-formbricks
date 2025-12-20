"""Chatwoot contact synchronization utilities."""

import frappe
from frappe import _
from frappe.utils import now_datetime

from erpnext_chatwoot_formbricks.chatwoot.api import ChatwootAPI


def create_erpnext_contact(chatwoot_contact):
	"""Create a Customer or Lead in ERPNext from Chatwoot contact.

	Args:
		chatwoot_contact: Contact data from Chatwoot webhook
	"""
	settings = frappe.get_single("Chatwoot Settings")
	if not settings.enabled:
		return None

	contact_id = str(chatwoot_contact.get("id"))
	name = chatwoot_contact.get("name") or "Unknown"
	email = chatwoot_contact.get("email")
	phone = chatwoot_contact.get("phone_number")

	# Check if already exists
	if _contact_exists(contact_id, email):
		return None

	if settings.auto_create_lead:
		return _create_lead(contact_id, name, email, phone, chatwoot_contact)
	elif settings.auto_create_customer:
		return _create_customer(contact_id, name, email, phone, chatwoot_contact, settings)

	return None


def update_erpnext_contact(chatwoot_contact):
	"""Update an existing Customer or Lead from Chatwoot contact.

	Args:
		chatwoot_contact: Contact data from Chatwoot webhook
	"""
	contact_id = str(chatwoot_contact.get("id"))
	name = chatwoot_contact.get("name")
	email = chatwoot_contact.get("email")
	phone = chatwoot_contact.get("phone_number")

	# Find and update Customer
	customer = frappe.db.get_value("Customer", {"chatwoot_contact_id": contact_id}, "name")
	if customer:
		updates = {}
		if name:
			updates["customer_name"] = name
		if email:
			updates["email_id"] = email
		if phone:
			updates["mobile_no"] = phone
		if updates:
			frappe.db.set_value("Customer", customer, updates)
			frappe.db.commit()
		return customer

	# Find and update Lead
	lead = frappe.db.get_value("Lead", {"chatwoot_contact_id": contact_id}, "name")
	if lead:
		updates = {}
		if name:
			updates["lead_name"] = name
		if email:
			updates["email_id"] = email
		if phone:
			updates["mobile_no"] = phone
		if updates:
			frappe.db.set_value("Lead", lead, updates)
			frappe.db.commit()
		return lead

	return None


def sync_contacts_from_chatwoot():
	"""Sync all contacts from Chatwoot to ERPNext.

	This is called by the scheduler.
	"""
	settings = frappe.get_single("Chatwoot Settings")
	if not settings.enabled:
		return

	api = ChatwootAPI(settings)
	page = 1
	total_synced = 0

	while True:
		try:
			response = api.get_contacts(page=page)
			contacts = response.get("payload", [])

			if not contacts:
				break

			for contact in contacts:
				try:
					if not _contact_exists(str(contact.get("id")), contact.get("email")):
						create_erpnext_contact(contact)
						total_synced += 1
				except Exception as e:
					frappe.log_error(f"Error syncing contact {contact.get('id')}: {e}")

			# Check for more pages
			meta = response.get("meta", {})
			if page >= meta.get("total_pages", 1):
				break

			page += 1

		except Exception as e:
			frappe.log_error(f"Error fetching contacts from Chatwoot: {e}")
			break

	# Update last sync time
	frappe.db.set_value("Chatwoot Settings", None, "last_sync", now_datetime())
	frappe.db.commit()

	return total_synced


def sync_customer_to_chatwoot(doc, method=None):
	"""Sync ERPNext Customer to Chatwoot.

	This is called via doc_events hook.

	Args:
		doc: Customer document
		method: Event method (after_insert, on_update)
	"""
	settings = frappe.get_single("Chatwoot Settings")
	if not settings.enabled:
		return

	# Skip if already has Chatwoot ID (was created from Chatwoot)
	if doc.chatwoot_contact_id:
		return

	try:
		api = ChatwootAPI(settings)

		# Check if contact already exists by email
		if doc.email_id:
			existing = api.search_contacts(doc.email_id)
			contacts = existing.get("payload", [])
			if contacts:
				# Link to existing contact
				contact_id = str(contacts[0].get("id"))
				frappe.db.set_value("Customer", doc.name, "chatwoot_contact_id", contact_id)
				frappe.db.commit()
				return

		# Create new contact
		result = api.create_contact(
			name=doc.customer_name,
			email=doc.email_id,
			phone=doc.mobile_no,
			identifier=doc.name,
			custom_attributes={
				"erpnext_customer": doc.name,
				"customer_group": doc.customer_group,
			}
		)

		if result:
			contact_id = str(result.get("payload", {}).get("contact", {}).get("id", ""))
			if contact_id:
				frappe.db.set_value("Customer", doc.name, "chatwoot_contact_id", contact_id)
				frappe.db.commit()

	except Exception as e:
		frappe.log_error(f"Error syncing Customer {doc.name} to Chatwoot: {e}")


def _contact_exists(chatwoot_contact_id, email):
	"""Check if contact already exists in ERPNext.

	Args:
		chatwoot_contact_id: Chatwoot contact ID
		email: Contact email

	Returns:
		True if contact exists, False otherwise
	"""
	# Check by Chatwoot ID
	if frappe.db.exists("Customer", {"chatwoot_contact_id": chatwoot_contact_id}):
		return True
	if frappe.db.exists("Lead", {"chatwoot_contact_id": chatwoot_contact_id}):
		return True

	# Check by email
	if email:
		if frappe.db.exists("Customer", {"email_id": email}):
			return True
		if frappe.db.exists("Lead", {"email_id": email}):
			return True

	return False


def _create_customer(contact_id, name, email, phone, chatwoot_contact, settings):
	"""Create a Customer from Chatwoot contact.

	Args:
		contact_id: Chatwoot contact ID
		name: Contact name
		email: Contact email
		phone: Contact phone
		chatwoot_contact: Full contact data
		settings: Chatwoot Settings document
	"""
	try:
		customer = frappe.new_doc("Customer")
		customer.customer_name = name
		customer.customer_type = "Individual"

		if settings.customer_group:
			customer.customer_group = settings.customer_group
		else:
			customer.customer_group = frappe.db.get_single_value("Selling Settings", "customer_group") or "All Customer Groups"

		customer.territory = frappe.db.get_single_value("Selling Settings", "territory") or "All Territories"

		if email:
			customer.email_id = email
		if phone:
			customer.mobile_no = phone

		customer.chatwoot_contact_id = contact_id
		customer.insert(ignore_permissions=True)
		frappe.db.commit()

		return customer.name

	except Exception as e:
		frappe.log_error(f"Error creating Customer from Chatwoot contact {contact_id}: {e}")
		return None


def _create_lead(contact_id, name, email, phone, chatwoot_contact):
	"""Create a Lead from Chatwoot contact.

	Args:
		contact_id: Chatwoot contact ID
		name: Contact name
		email: Contact email
		phone: Contact phone
		chatwoot_contact: Full contact data
	"""
	try:
		lead = frappe.new_doc("Lead")
		lead.lead_name = name
		lead.source = "Chat"

		if email:
			lead.email_id = email
		if phone:
			lead.mobile_no = phone

		lead.chatwoot_contact_id = contact_id
		lead.insert(ignore_permissions=True)
		frappe.db.commit()

		return lead.name

	except Exception as e:
		frappe.log_error(f"Error creating Lead from Chatwoot contact {contact_id}: {e}")
		return None
