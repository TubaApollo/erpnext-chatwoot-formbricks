"""Chatwoot contact synchronization utilities."""

import frappe
from frappe import _
from frappe.utils import now_datetime

from erpnext_chatwoot_formbricks.chatwoot.api import ChatwootAPI


def create_erpnext_contact(chatwoot_contact):
	"""Link Chatwoot contact to existing ERPNext Customer by email.

	Only links if:
	- Email is provided in Chatwoot contact
	- A Customer with that email already exists in ERPNext

	Args:
		chatwoot_contact: Contact data from Chatwoot webhook

	Returns:
		Customer name if linked, None otherwise
	"""
	settings = frappe.get_single("Chatwoot Settings")
	if not settings.enabled:
		return None

	contact_id = str(chatwoot_contact.get("id"))
	email = chatwoot_contact.get("email")

	# Only proceed if email is provided
	if not email:
		return None

	# Check if already linked by Chatwoot ID
	existing_customer = frappe.db.get_value("Customer", {"chatwoot_contact_id": contact_id}, "name")
	if existing_customer:
		return existing_customer

	# Find existing Customer by email using common function
	from erpnext_chatwoot_formbricks.common.contact_sync import find_erpnext_contact_by_email
	doctype, name = find_erpnext_contact_by_email(email)

	if doctype == "Customer" and name:
		frappe.db.set_value("Customer", name, "chatwoot_contact_id", contact_id)
		frappe.db.commit()
		return name

	# No matching Customer found - do nothing
	return None


def update_erpnext_contact(chatwoot_contact):
	"""Update an existing linked Customer from Chatwoot contact.

	Only updates if Customer is already linked via chatwoot_contact_id.

	Args:
		chatwoot_contact: Contact data from Chatwoot webhook

	Returns:
		Customer name if updated, None otherwise
	"""
	contact_id = str(chatwoot_contact.get("id"))
	name = chatwoot_contact.get("name")
	email = chatwoot_contact.get("email")
	phone = chatwoot_contact.get("phone_number")

	# Find and update Customer (only if already linked)
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

	return None


def sync_contacts_from_chatwoot():
	"""Sync contacts from Chatwoot to ERPNext.

	Only links Chatwoot contacts to existing ERPNext Customers by email.
	Does not create new Customers.

	This is called by the scheduler.
	"""
	settings = frappe.get_single("Chatwoot Settings")
	if not settings.enabled:
		return

	api = ChatwootAPI(settings)
	page = 1
	total_linked = 0

	while True:
		try:
			response = api.get_contacts(page=page)
			contacts = response.get("payload", [])

			if not contacts:
				break

			for contact in contacts:
				try:
					result = create_erpnext_contact(contact)
					if result:
						total_linked += 1
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

	return total_linked


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


