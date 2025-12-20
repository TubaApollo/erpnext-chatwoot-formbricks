"""Formbricks webhook handler for incoming events."""

import hashlib
import hmac
import json

import frappe
from frappe import _


@frappe.whitelist(allow_guest=True)
def handle():
	"""Handle incoming Formbricks webhooks.

	This endpoint receives webhook events from Formbricks and processes them accordingly.
	"""
	# Get request data
	try:
		data = frappe.request.get_json()
	except Exception:
		frappe.throw(_("Invalid JSON payload"), frappe.InvalidRequestError)

	if not data:
		frappe.throw(_("Empty payload"), frappe.InvalidRequestError)

	# Verify webhook signature if configured
	settings = frappe.get_single("Formbricks Settings")
	if not settings.enabled:
		return {"status": "error", "message": "Formbricks integration is disabled"}

	if settings.webhook_secret:
		if not _verify_signature(settings.get_password("webhook_secret")):
			frappe.throw(_("Invalid webhook signature"), frappe.AuthenticationError)

	# Get event type
	event_type = data.get("webhookEvent") or data.get("event")
	if not event_type:
		return {"status": "error", "message": "No event type in payload"}

	# Log the webhook for debugging
	frappe.log_error(
		message=json.dumps(data, indent=2),
		title=f"Formbricks Webhook: {event_type}"
	)

	# Process event based on type
	try:
		if event_type == "responseCreated":
			_handle_response_created(data)
		elif event_type == "responseUpdated":
			_handle_response_updated(data)
		elif event_type == "responseFinished":
			_handle_response_finished(data)
		else:
			frappe.log_error(
				message=f"Unhandled event type: {event_type}\n{json.dumps(data, indent=2)}",
				title="Formbricks Webhook: Unknown Event"
			)

		return {"status": "success", "event": event_type}

	except Exception as e:
		frappe.log_error(
			message=f"Error processing webhook: {str(e)}\n{json.dumps(data, indent=2)}",
			title=f"Formbricks Webhook Error: {event_type}"
		)
		return {"status": "error", "message": str(e)}


def _verify_signature(secret):
	"""Verify the webhook signature from Formbricks."""
	signature = frappe.request.headers.get("X-Formbricks-Signature")
	if not signature:
		return False

	payload = frappe.request.get_data()
	expected_signature = hmac.new(
		secret.encode("utf-8"),
		payload,
		hashlib.sha256
	).hexdigest()

	return hmac.compare_digest(signature, expected_signature)


def _handle_response_created(data):
	"""Handle responseCreated event.

	Creates a new Formbricks Response document in ERPNext.
	"""
	from erpnext_chatwoot_formbricks.formbricks.response import create_or_update_response

	response_data = data.get("data", {})
	create_or_update_response(response_data)


def _handle_response_updated(data):
	"""Handle responseUpdated event."""
	from erpnext_chatwoot_formbricks.formbricks.response import create_or_update_response

	response_data = data.get("data", {})
	create_or_update_response(response_data)


def _handle_response_finished(data):
	"""Handle responseFinished event.

	Finalizes the response and optionally creates a Lead.
	"""
	from erpnext_chatwoot_formbricks.formbricks.response import finalize_response

	response_data = data.get("data", {})
	finalize_response(response_data)
