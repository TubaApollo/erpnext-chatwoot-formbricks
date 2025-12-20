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
	try:
		data = frappe.request.get_json()
	except Exception:
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
	"""
	from erpnext_chatwoot_formbricks.chatwoot.conversation import create_or_update_conversation

	conversation = data.get("conversation", {})
	contact = data.get("sender", {}) or conversation.get("meta", {}).get("sender", {})

	create_or_update_conversation(conversation, contact)


def _handle_conversation_updated(data):
	"""Handle conversation_updated event."""
	from erpnext_chatwoot_formbricks.chatwoot.conversation import create_or_update_conversation

	conversation = data.get("conversation", {})
	contact = data.get("sender", {}) or conversation.get("meta", {}).get("sender", {})

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
	Can also trigger lead creation based on settings.
	"""
	from erpnext_chatwoot_formbricks.chatwoot.conversation import add_message_to_conversation
	from erpnext_chatwoot_formbricks.common.lead_creation import maybe_create_lead_from_conversation

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

		# Check if we should create a lead
		settings = frappe.get_single("Chatwoot Settings")
		if settings.auto_create_lead:
			maybe_create_lead_from_conversation(conversation, sender)


def _handle_contact_created(data):
	"""Handle contact_created event.

	Creates a new Customer or Lead in ERPNext based on settings.
	"""
	from erpnext_chatwoot_formbricks.chatwoot.contact import create_erpnext_contact

	contact = data.get("contact", {})
	if contact:
		create_erpnext_contact(contact)


def _handle_contact_updated(data):
	"""Handle contact_updated event.

	Updates the corresponding Customer or Lead in ERPNext.
	"""
	from erpnext_chatwoot_formbricks.chatwoot.contact import update_erpnext_contact

	contact = data.get("contact", {})
	if contact:
		update_erpnext_contact(contact)
