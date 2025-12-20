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

	# Check if response exists
	existing = frappe.db.exists("Formbricks Response", {"response_id": response_id})

	if existing:
		doc = frappe.get_doc("Formbricks Response", existing)
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
	"""
	# Common field names for contact information
	email_fields = ["email", "e-mail", "emailAddress", "email_address", "contact_email"]
	name_fields = ["name", "fullName", "full_name", "firstName", "first_name", "contact_name"]
	phone_fields = ["phone", "phoneNumber", "phone_number", "mobile", "telephone", "contact_phone"]

	# Extract email
	for field in email_fields:
		value = data.get(field)
		if value and isinstance(value, str) and "@" in value:
			doc.contact_email = value
			break

	# Extract name
	for field in name_fields:
		value = data.get(field)
		if value and isinstance(value, str):
			doc.contact_name = value
			break

	# Extract phone
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

	# Check for existing Customer
	customer = frappe.db.get_value("Customer", {"email_id": email}, "name")
	if customer:
		doc.customer = customer
		return

	# Check for existing Lead
	lead = frappe.db.get_value("Lead", {"email_id": email}, "name")
	if lead:
		doc.lead = lead
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

		if settings.lead_source:
			lead.source = settings.lead_source
		else:
			lead.source = "Survey"

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
		timestamp: Timestamp string or ISO format
	"""
	if not timestamp:
		return None

	try:
		return get_datetime(timestamp)
	except Exception:
		return now_datetime()
