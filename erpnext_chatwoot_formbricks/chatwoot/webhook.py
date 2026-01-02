"""Chatwoot webhook handler for incoming events."""

import hashlib
import hmac
import json

import frappe
from frappe import _


@frappe.whitelist(allow_guest=True)
def handle():
	"""Handle incoming Chatwoot webhooks.

	This endpoint receives webhook events from Chatwoot and processes them accordingly.
	"""
	# Get request data
	data = None
	try:
		# Try multiple methods to get JSON data
		if hasattr(frappe.request, 'get_json'):
			data = frappe.request.get_json(force=True, silent=True)
		if not data:
			raw_data = frappe.request.get_data(as_text=True)
			if raw_data:
				data = json.loads(raw_data)
	except Exception as e:
		frappe.log_error(f"Failed to parse webhook JSON: {e}", "Chatwoot Webhook JSON Error")
		frappe.throw(_("Invalid JSON payload"), frappe.InvalidRequestError)

	if not data:
		frappe.throw(_("Empty payload"), frappe.InvalidRequestError)

	# Verify webhook signature if configured
	settings = frappe.get_single("Chatwoot Settings")
	if not settings.enabled:
		return {"status": "error", "message": "Chatwoot integration is disabled"}

	if settings.webhook_secret:
		if not _verify_signature(settings.get_password("webhook_secret")):
			frappe.throw(_("Invalid webhook signature"), frappe.AuthenticationError)

	# Get event type
	event_type = data.get("event")
	if not event_type:
		return {"status": "error", "message": "No event type in payload"}

	# Log the webhook for debugging
	frappe.log_error(
		message=json.dumps(data, indent=2),
		title=f"Chatwoot Webhook: {event_type}"
	)

	# Process event based on type
	try:
		if event_type == "conversation_created":
			_handle_conversation_created(data)
		elif event_type == "conversation_updated":
			_handle_conversation_updated(data)
		elif event_type == "conversation_status_changed":
			_handle_conversation_status_changed(data)
		elif event_type == "message_created":
			_handle_message_created(data)
		elif event_type == "contact_created":
			_handle_contact_created(data)
		elif event_type == "contact_updated":
			_handle_contact_updated(data)
		else:
			frappe.log_error(
				message=f"Unhandled event type: {event_type}\n{json.dumps(data, indent=2)}",
				title="Chatwoot Webhook: Unknown Event"
			)

		return {"status": "success", "event": event_type}

	except Exception as e:
		frappe.log_error(
			message=f"Error processing webhook: {str(e)}\n{json.dumps(data, indent=2)}",
			title=f"Chatwoot Webhook Error: {event_type}"
		)
		return {"status": "error", "message": str(e)}


def _verify_signature(secret):
	"""Verify the webhook signature from Chatwoot.

	Chatwoot sends a signature in the X-Chatwoot-Webhook-Signature header.
	"""
	signature = frappe.request.headers.get("X-Chatwoot-Webhook-Signature")
	if not signature:
		return False

	payload = frappe.request.get_data()
	expected_signature = hmac.new(
		secret.encode("utf-8"),
		payload,
		hashlib.sha256
	).hexdigest()

	return hmac.compare_digest(signature, expected_signature)


def _handle_conversation_created(data):
	"""Handle conversation_created event.

	Creates a new Chatwoot Conversation document in ERPNext.
	Also creates an Issue if sync_conversations_as_issues is enabled.
	"""
	from erpnext_chatwoot_formbricks.chatwoot.conversation import create_or_update_conversation

	# conversation_created sends data directly or under "conversation" key
	conversation = data.get("conversation") or data

	# Get contact/sender info from various possible locations
	contact = (
		data.get("sender") or
		data.get("meta", {}).get("sender") or
		conversation.get("meta", {}).get("sender") or
		{}
	)

	conv_doc = create_or_update_conversation(conversation, contact)

	# Create Issue if enabled
	settings = frappe.get_single("Chatwoot Settings")
	if settings.sync_conversations_as_issues and conv_doc:
		_create_issue_from_conversation(conv_doc, conversation, contact, settings)


def _handle_conversation_updated(data):
	"""Handle conversation_updated event."""
	from erpnext_chatwoot_formbricks.chatwoot.conversation import create_or_update_conversation

	# Event may send data directly or under "conversation" key
	conversation = data.get("conversation") or data

	# Get contact/sender info from various possible locations
	contact = (
		data.get("sender") or
		data.get("meta", {}).get("sender") or
		conversation.get("meta", {}).get("sender") or
		{}
	)

	create_or_update_conversation(conversation, contact)


def _handle_conversation_status_changed(data):
	"""Handle conversation_status_changed event."""
	from erpnext_chatwoot_formbricks.chatwoot.conversation import update_conversation_status

	conversation = data.get("conversation", {})
	conversation_id = conversation.get("id")
	status = conversation.get("status")

	if conversation_id and status:
		update_conversation_status(conversation_id, status)


def _handle_message_created(data):
	"""Handle message_created event.

	Creates a new message in the corresponding conversation.
	Also adds message as comment to linked Issue.
	"""
	from erpnext_chatwoot_formbricks.chatwoot.conversation import add_message_to_conversation

	message = data.get("content") or data.get("message", {}).get("content", "")
	conversation = data.get("conversation", {})
	sender = data.get("sender", {})

	if conversation and message:
		add_message_to_conversation(
			conversation_id=conversation.get("id"),
			message_id=data.get("id"),
			content=message,
			message_type=data.get("message_type", "incoming"),
			sender_type=sender.get("type", "contact"),
			sender_id=sender.get("id"),
			sender_name=sender.get("name"),
			created_at=data.get("created_at"),
		)

		# Add message as comment to linked Issue
		_add_message_to_issue(conversation.get("id"), message, sender, data.get("message_type", "incoming"))


def _handle_contact_created(data):
	"""Handle contact_created event.

	Creates a new Customer or Lead in ERPNext based on settings.
	Note: For contact_created events, Chatwoot may send the contact data
	directly at the root level or inside a "contact" key.
	"""
	from erpnext_chatwoot_formbricks.chatwoot.contact import create_erpnext_contact

	# Check for "contact" key first (for backward compatibility), then use root data
	contact = data.get("contact")
	if not contact and data.get("id"):
		# Contact data is at root level
		contact = data

	if contact:
		create_erpnext_contact(contact)


def _handle_contact_updated(data):
	"""Handle contact_updated event.

	Updates the corresponding Customer or Lead in ERPNext.
	Note: For contact_updated events, Chatwoot sends the contact data
	directly at the root level, not inside a "contact" key.
	"""
	from erpnext_chatwoot_formbricks.chatwoot.contact import update_erpnext_contact

	# For contact_updated events, the contact data is at the root level
	# Check for "contact" key first (for backward compatibility), then use root data
	contact = data.get("contact")
	if not contact and data.get("id"):
		# Contact data is at root level
		contact = data

	if contact:
		update_erpnext_contact(contact)


def _create_issue_from_conversation(conv_doc, conversation_data, contact_data, settings):
	"""Create an Issue from a Chatwoot conversation.

	Args:
		conv_doc: Chatwoot Conversation document
		conversation_data: Raw conversation data from webhook
		contact_data: Contact data from webhook
		settings: Chatwoot Settings document
	"""
	conversation_id = str(conversation_data.get("id"))

	# Check if Issue already exists for this conversation
	existing_issue = frappe.db.exists("Issue", {"chatwoot_conversation_id": conversation_id})
	if existing_issue:
		return existing_issue

	try:
		# Build subject from contact info
		contact_name = contact_data.get("name", "Unknown")
		contact_email = contact_data.get("email", "")
		inbox_name = conv_doc.inbox_name or "Chatwoot"

		subject = f"[{inbox_name}] Conversation with {contact_name}"
		if contact_email:
			subject += f" ({contact_email})"

		# Create the Issue
		issue = frappe.new_doc("Issue")
		issue.subject = subject
		issue.raised_by = contact_email or ""
		issue.chatwoot_conversation_id = conversation_id

		# Set Issue Type if configured
		if settings.issue_type:
			issue.issue_type = settings.issue_type

		# Link to Customer if available
		if conv_doc.customer:
			issue.customer = conv_doc.customer

		# Set description with conversation link
		chatwoot_url = settings.api_url.rstrip("/")
		account_id = settings.account_id
		conv_link = f"{chatwoot_url}/app/accounts/{account_id}/conversations/{conversation_id}"

		issue.description = f"""<p>New conversation from Chatwoot</p>
<p><strong>Contact:</strong> {contact_name}</p>
<p><strong>Email:</strong> {contact_email or 'N/A'}</p>
<p><strong>Inbox:</strong> {inbox_name}</p>
<p><a href="{conv_link}">View in Chatwoot</a></p>"""

		issue.insert(ignore_permissions=True)
		frappe.db.commit()

		return issue.name

	except Exception as e:
		frappe.log_error(
			f"Error creating Issue from conversation {conversation_id}: {e}",
			"Chatwoot Issue Creation Error"
		)


def _add_message_to_issue(conversation_id, message, sender, message_type):
	"""Add a Chatwoot message as a comment to the linked Issue.

	Args:
		conversation_id: Chatwoot conversation ID
		message: Message content
		sender: Sender data from webhook
		message_type: Type of message (incoming/outgoing)
	"""
	if not conversation_id:
		return

	conversation_id = str(conversation_id)

	# Find the Issue linked to this conversation
	issue_name = frappe.db.get_value("Issue", {"chatwoot_conversation_id": conversation_id}, "name")
	if not issue_name:
		return

	try:
		sender_name = sender.get("name", "Unknown")
		sender_type = sender.get("type", "contact")

		# Format the comment based on sender type
		if sender_type in ("agent", "agent_bot", "bot"):
			icon = "🤖" if sender_type in ("agent_bot", "bot") else "👤"
			comment_content = f"<p><strong>{icon} {sender_name}:</strong></p><p>{message}</p>"
		else:
			comment_content = f"<p><strong>💬 {sender_name}:</strong></p><p>{message}</p>"

		# Add as comment to the Issue
		comment = frappe.get_doc({
			"doctype": "Comment",
			"comment_type": "Comment",
			"reference_doctype": "Issue",
			"reference_name": issue_name,
			"content": comment_content,
		})
		comment.insert(ignore_permissions=True)
		frappe.db.commit()

	except Exception as e:
		frappe.log_error(
			f"Error adding message to Issue {issue_name}: {e}",
			"Chatwoot Issue Comment Error"
		)
