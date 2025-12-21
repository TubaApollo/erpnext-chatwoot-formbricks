"""Formbricks response management utilities."""

import json

import frappe
from frappe.utils import now_datetime, get_datetime


def create_or_update_response(response_data):
	"""Create or update a Formbricks Response document.

	Args:
		response_data: Response data from Formbricks webhook
	"""
	response_id = response_data.get("id") or response_data.get("responseId")
	if not response_id:
		return None

	response_id = str(response_id)

	# Document name follows autoname format: FBRESP-{response_id}
	doc_name = f"FBRESP-{response_id}"

	# Check if response exists by name (more reliable than field lookup)
	if frappe.db.exists("Formbricks Response", doc_name):
		doc = frappe.get_doc("Formbricks Response", doc_name)
	else:
		doc = frappe.new_doc("Formbricks Response")
		doc.response_id = response_id

	# Update fields
	survey_id = response_data.get("surveyId")
	if survey_id:
		# Link to survey if exists
		survey_doc = frappe.db.exists("Formbricks Survey", {"survey_id": survey_id})
		if survey_doc:
			doc.survey = survey_doc

	# Store response data as JSON
	data = response_data.get("data", {})
	doc.data_json = json.dumps(data, indent=2)

	# Extract contact information from data
	_extract_contact_info(doc, data)

	# Timestamps
	if response_data.get("createdAt"):
		doc.created_at = _parse_timestamp(response_data.get("createdAt"))

	doc.finished = response_data.get("finished", False)
	if doc.finished and response_data.get("finishedAt"):
		doc.finished_at = _parse_timestamp(response_data.get("finishedAt"))

	# Link to existing Customer or Lead if possible
	_link_to_erpnext_contact(doc)

	try:
		doc.save(ignore_permissions=True)
		frappe.db.commit()
	except frappe.DuplicateEntryError:
		# Race condition: document was created by another webhook event
		# Fetch and update the existing document
		frappe.db.rollback()
		doc_name = f"FBRESP-{response_id}"
		doc = frappe.get_doc("Formbricks Response", doc_name)
		# Update with new data
		if response_data.get("finished"):
			doc.finished = True
		if response_data.get("finishedAt"):
			doc.finished_at = _parse_timestamp(response_data.get("finishedAt"))
		doc.save(ignore_permissions=True)
		frappe.db.commit()

	return doc


def finalize_response(response_data):
	"""Finalize a response and optionally create a Lead.

	Args:
		response_data: Response data from Formbricks webhook
	"""
	doc = create_or_update_response(response_data)
	if not doc:
		return None

	doc.finished = True
	doc.finished_at = now_datetime()
	doc.save(ignore_permissions=True)

	# Check if we should create a lead
	settings = frappe.get_single("Formbricks Settings")
	if settings.auto_create_lead and not doc.lead and not doc.customer:
		_maybe_create_lead(doc, settings)

	frappe.db.commit()
	return doc


def _extract_contact_info(doc, data):
	"""Extract contact information from response data.

	Args:
		doc: Formbricks Response document
		data: Response data dictionary

	Handles both simple string fields and Formbricks array format:
	e.g., "contactinfo01ab": ["firstname", "lastname", "email@mail.com", "phone", "company"]
	"""
	# Common field names for contact information
	email_fields = ["email", "e-mail", "emailAddress", "email_address", "contact_email"]
	name_fields = ["name", "fullName", "full_name", "firstName", "first_name", "contact_name"]
	phone_fields = ["phone", "phoneNumber", "phone_number", "mobile", "telephone", "contact_phone"]

	# First, check for Formbricks contact info array fields
	# These typically have names like "contactinfo01ab" and contain [firstname, lastname, email, phone, company]
	for field_name, value in data.items():
		if isinstance(value, list) and len(value) >= 3:
			# Check if this looks like a contact info array
			if "contact" in field_name.lower() or "info" in field_name.lower():
				# Typical format: [firstname, lastname, email, phone, company]
				if len(value) >= 1 and value[0]:
					firstname = str(value[0]).strip()
					lastname = str(value[1]).strip() if len(value) > 1 and value[1] else ""
					if firstname or lastname:
						doc.contact_name = f"{firstname} {lastname}".strip()
				if len(value) >= 3 and value[2] and "@" in str(value[2]):
					doc.contact_email = str(value[2]).strip()
				if len(value) >= 4 and value[3]:
					doc.contact_phone = str(value[3]).strip()
				break  # Found contact info array, stop looking

	# If not found in array, try simple string fields
	if not doc.contact_email:
		for field in email_fields:
			value = data.get(field)
			if value and isinstance(value, str) and "@" in value:
				doc.contact_email = value
				break

	# Also search all values for email if still not found
	if not doc.contact_email:
		for value in data.values():
			if isinstance(value, str) and "@" in value and "." in value.split("@")[-1]:
				doc.contact_email = value
				break

	# Extract name if not already set
	if not doc.contact_name:
		for field in name_fields:
			value = data.get(field)
			if value and isinstance(value, str):
				doc.contact_name = value
				break

	# Extract phone if not already set
	if not doc.contact_phone:
		for field in phone_fields:
			value = data.get(field)
			if value and isinstance(value, str):
				doc.contact_phone = value
				break


def _link_to_erpnext_contact(doc):
	"""Link response to ERPNext Customer or Lead.

	Args:
		doc: Formbricks Response document
	"""
	if doc.customer or doc.lead:
		return

	email = doc.contact_email
	if not email:
		return

	# Find existing Customer or Lead by email using common function
	from erpnext_chatwoot_formbricks.common.contact_sync import find_erpnext_contact_by_email
	doctype, name = find_erpnext_contact_by_email(email)

	if doctype == "Customer" and name:
		doc.customer = name
		return

	if doctype == "Lead" and name:
		doc.lead = name
		return


def _maybe_create_lead(doc, settings):
	"""Create a Lead from response if configured.

	Args:
		doc: Formbricks Response document
		settings: Formbricks Settings document
	"""
	# Check if this survey should create leads
	if settings.lead_survey_ids:
		allowed_surveys = [s.strip() for s in settings.lead_survey_ids.split(",")]
		survey_id = frappe.db.get_value("Formbricks Survey", doc.survey, "survey_id") if doc.survey else None
		if survey_id and survey_id not in allowed_surveys:
			return

	# Need at least an email to create a lead
	if not doc.contact_email:
		return

	# Check if lead already exists
	existing_lead = frappe.db.get_value("Lead", {"email_id": doc.contact_email}, "name")
	if existing_lead:
		doc.lead = existing_lead
		frappe.db.set_value("Lead", existing_lead, "formbricks_response_id", doc.response_id)
		return

	# Create new Lead
	try:
		lead = frappe.new_doc("Lead")
		lead.lead_name = doc.contact_name or doc.contact_email.split("@")[0]
		lead.email_id = doc.contact_email

		if doc.contact_phone:
			lead.mobile_no = doc.contact_phone

		# Set lead source
		if settings.lead_source and frappe.db.exists("Lead Source", settings.lead_source):
			lead.source = settings.lead_source
		else:
			# Try common fallback sources
			for source in ["Campaign", "Advertisement", "Website"]:
				if frappe.db.exists("Lead Source", source):
					lead.source = source
					break

		lead.formbricks_contact_id = ""
		lead.formbricks_response_id = doc.response_id

		lead.insert(ignore_permissions=True)
		frappe.db.commit()

		doc.lead = lead.name
		doc.save(ignore_permissions=True)
		frappe.db.commit()

	except Exception as e:
		frappe.log_error(f"Error creating Lead from Formbricks response {doc.response_id}: {e}")


def _parse_timestamp(timestamp):
	"""Parse timestamp from Formbricks format.

	Args:
		timestamp: Timestamp string or ISO format (e.g., '2025-12-20T23:27:30.601Z')
	"""
	if not timestamp:
		return None

	try:
		timestamp_str = str(timestamp)

		# Remove timezone info (MariaDB doesn't support it)
		# Handle ISO format with Z suffix
		if timestamp_str.endswith('Z'):
			timestamp_str = timestamp_str[:-1]
		# Handle +00:00 style timezone
		elif '+' in timestamp_str:
			timestamp_str = timestamp_str.rsplit('+', 1)[0]
		elif timestamp_str.count('-') > 2:
			# Handle -00:00 style timezone at the end
			parts = timestamp_str.rsplit('-', 1)
			if ':' in parts[-1] and len(parts[-1]) <= 6:
				timestamp_str = parts[0]

		# Replace T with space for standard datetime format
		timestamp_str = timestamp_str.replace('T', ' ')

		# Truncate microseconds if too long (max 6 digits)
		if '.' in timestamp_str:
			parts = timestamp_str.split('.')
			if len(parts[1]) > 6:
				parts[1] = parts[1][:6]
			timestamp_str = '.'.join(parts)

		return get_datetime(timestamp_str)
	except Exception:
		return now_datetime()
