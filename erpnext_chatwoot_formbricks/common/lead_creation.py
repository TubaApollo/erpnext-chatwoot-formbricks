"""Common lead creation utilities for both Chatwoot and Formbricks."""

import frappe
from frappe import _


def maybe_create_lead_from_conversation(conversation_data, contact_data):
	"""Create a Lead from a Chatwoot conversation if configured.

	Args:
		conversation_data: Conversation data from Chatwoot
		contact_data: Contact data from Chatwoot
	"""
	settings = frappe.get_single("Chatwoot Settings")
	if not settings.auto_create_lead:
		return None

	email = contact_data.get("email")
	phone = contact_data.get("phone_number")
	name = contact_data.get("name", "Unknown")
	contact_id = str(contact_data.get("id", ""))
	conversation_id = str(conversation_data.get("id", ""))

	# Check if lead already exists
	if contact_id:
		existing = frappe.db.get_value("Lead", {"chatwoot_contact_id": contact_id}, "name")
		if existing:
			return existing

	if email:
		existing = frappe.db.get_value("Lead", {"email_id": email}, "name")
		if existing:
			# Update with Chatwoot IDs
			frappe.db.set_value("Lead", existing, {
				"chatwoot_contact_id": contact_id,
				"chatwoot_conversation_id": conversation_id,
			})
			frappe.db.commit()
			return existing

	# Need at least email or phone to create a lead
	if not email and not phone:
		return None

	try:
		lead = frappe.new_doc("Lead")
		lead.lead_name = name
		lead.source = "Chat"

		if email:
			lead.email_id = email
		if phone:
			lead.mobile_no = phone

		lead.chatwoot_contact_id = contact_id
		lead.chatwoot_conversation_id = conversation_id

		lead.insert(ignore_permissions=True)
		frappe.db.commit()

		return lead.name

	except Exception as e:
		frappe.log_error(f"Error creating Lead from Chatwoot conversation: {e}")
		return None


def create_opportunity_from_lead(lead_name, opportunity_type="Sales"):
	"""Create an Opportunity from an existing Lead.

	Args:
		lead_name: Name of the Lead document
		opportunity_type: Type of opportunity (Sales, Maintenance, etc.)
	"""
	try:
		lead = frappe.get_doc("Lead", lead_name)

		opportunity = frappe.new_doc("Opportunity")
		opportunity.opportunity_from = "Lead"
		opportunity.party_name = lead_name
		opportunity.opportunity_type = opportunity_type
		opportunity.status = "Open"

		# Copy contact information
		opportunity.contact_email = lead.email_id
		opportunity.contact_mobile = lead.mobile_no

		opportunity.insert(ignore_permissions=True)
		frappe.db.commit()

		return opportunity.name

	except Exception as e:
		frappe.log_error(f"Error creating Opportunity from Lead {lead_name}: {e}")
		return None


def score_lead_from_survey(lead_name, response_data):
	"""Score a Lead based on survey response data.

	This is a simple scoring mechanism that can be extended.

	Args:
		lead_name: Name of the Lead document
		response_data: Response data dictionary from Formbricks
	"""
	score = 0

	# Score based on data completeness
	if response_data.get("email"):
		score += 10
	if response_data.get("phone") or response_data.get("phoneNumber"):
		score += 10
	if response_data.get("company") or response_data.get("companyName"):
		score += 15
	if response_data.get("budget") or response_data.get("projectBudget"):
		score += 20
	if response_data.get("timeline") or response_data.get("projectTimeline"):
		score += 15

	# Score based on urgency indicators
	urgency_keywords = ["urgent", "asap", "immediately", "soon", "quickly"]
	data_str = str(response_data).lower()
	for keyword in urgency_keywords:
		if keyword in data_str:
			score += 10
			break

	# Update lead with score if supported
	try:
		# Check if lead_score field exists
		if frappe.db.exists("Custom Field", {"dt": "Lead", "fieldname": "lead_score"}):
			frappe.db.set_value("Lead", lead_name, "lead_score", score)
			frappe.db.commit()
	except Exception:
		pass

	return score


@frappe.whitelist()
def convert_lead_to_customer(lead_name):
	"""Convert a Lead to a Customer.

	Args:
		lead_name: Name of the Lead document

	Returns:
		Name of the created Customer
	"""
	try:
		lead = frappe.get_doc("Lead", lead_name)

		customer = frappe.new_doc("Customer")
		customer.customer_name = lead.lead_name
		customer.customer_type = "Individual"

		# Copy contact information
		if lead.email_id:
			customer.email_id = lead.email_id
		if lead.mobile_no:
			customer.mobile_no = lead.mobile_no

		# Copy integration IDs
		if hasattr(lead, "chatwoot_contact_id") and lead.chatwoot_contact_id:
			customer.chatwoot_contact_id = lead.chatwoot_contact_id
		if hasattr(lead, "formbricks_contact_id") and lead.formbricks_contact_id:
			customer.formbricks_contact_id = lead.formbricks_contact_id

		# Set defaults
		customer.customer_group = frappe.db.get_single_value("Selling Settings", "customer_group") or "All Customer Groups"
		customer.territory = frappe.db.get_single_value("Selling Settings", "territory") or "All Territories"

		customer.insert(ignore_permissions=True)
		frappe.db.commit()

		# Update lead status
		lead.status = "Converted"
		lead.save(ignore_permissions=True)
		frappe.db.commit()

		return customer.name

	except Exception as e:
		frappe.log_error(f"Error converting Lead {lead_name} to Customer: {e}")
		frappe.throw(_("Failed to convert Lead: {0}").format(str(e)))
