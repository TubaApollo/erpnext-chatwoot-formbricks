"""Chatwoot conversation management utilities."""

import frappe
from frappe.utils import now_datetime, get_datetime


def create_or_update_conversation(conversation_data, contact_data=None):
	"""Create or update a Chatwoot Conversation document.

	Args:
		conversation_data: Conversation data from Chatwoot webhook
		contact_data: Contact data from Chatwoot webhook
	"""
	conversation_id = str(conversation_data.get("id"))
	if not conversation_id:
		return None

	# Check if conversation exists
	existing = frappe.db.exists("Chatwoot Conversation", {"conversation_id": conversation_id})

	if existing:
		doc = frappe.get_doc("Chatwoot Conversation", existing)
	else:
		doc = frappe.new_doc("Chatwoot Conversation")
		doc.conversation_id = conversation_id

	# Update fields
	doc.status = conversation_data.get("status", "open")
	doc.inbox_id = str(conversation_data.get("inbox_id", ""))

	# Get inbox name from meta
	meta = conversation_data.get("meta", {})
	inbox = meta.get("channel") or meta.get("inbox", {})
	if isinstance(inbox, dict):
		doc.inbox_name = inbox.get("name", "")
	else:
		doc.inbox_name = str(inbox) if inbox else ""

	# Contact information
	if contact_data:
		doc.contact_name = contact_data.get("name", "")
		doc.contact_email = contact_data.get("email", "")

		# Try to link to existing Customer or Lead
		contact_id = contact_data.get("id")
		if contact_id:
			_link_to_erpnext_contact(doc, contact_id, contact_data)

	# Timestamps
	if conversation_data.get("created_at"):
		doc.created_at = _parse_timestamp(conversation_data.get("created_at"))
	if conversation_data.get("updated_at"):
		doc.updated_at = _parse_timestamp(conversation_data.get("updated_at"))

	doc.save(ignore_permissions=True)
	frappe.db.commit()

	return doc


def update_conversation_status(conversation_id, status):
	"""Update the status of a conversation.

	Args:
		conversation_id: Chatwoot conversation ID
		status: New status (open, resolved, pending)
	"""
	conversation_id = str(conversation_id)
	existing = frappe.db.exists("Chatwoot Conversation", {"conversation_id": conversation_id})

	if existing:
		frappe.db.set_value("Chatwoot Conversation", existing, "status", status)
		frappe.db.set_value("Chatwoot Conversation", existing, "updated_at", now_datetime())
		frappe.db.commit()
		return True

	return False


def add_message_to_conversation(
	conversation_id,
	message_id,
	content,
	message_type="incoming",
	sender_type="contact",
	sender_id=None,
	sender_name=None,
	created_at=None,
):
	"""Add a message to a conversation.

	Args:
		conversation_id: Chatwoot conversation ID
		message_id: Chatwoot message ID
		content: Message content
		message_type: Type of message (incoming/outgoing/activity)
		sender_type: Type of sender (contact/agent/bot)
		sender_id: ID of the sender
		sender_name: Name of the sender
		created_at: Timestamp of the message
	"""
	conversation_id = str(conversation_id)
	existing = frappe.db.exists("Chatwoot Conversation", {"conversation_id": conversation_id})

	if not existing:
		# Create the conversation if it doesn't exist
		doc = frappe.new_doc("Chatwoot Conversation")
		doc.conversation_id = conversation_id
		doc.status = "open"
	else:
		doc = frappe.get_doc("Chatwoot Conversation", existing)

	# Check if message already exists
	message_exists = any(m.message_id == str(message_id) for m in doc.messages)
	if message_exists:
		return doc

	# Add the message
	doc.append("messages", {
		"message_id": str(message_id),
		"content": content or "",
		"message_type": message_type,
		"sender_type": sender_type,
		"sender_id": str(sender_id) if sender_id else "",
		"sender_name": sender_name or "",
		"created_at": _parse_timestamp(created_at) if created_at else now_datetime(),
	})

	doc.updated_at = now_datetime()
	doc.save(ignore_permissions=True)
	frappe.db.commit()

	return doc


def log_outgoing_message(conversation_id, content, result):
	"""Log an outgoing message sent from ERPNext.

	Args:
		conversation_id: Chatwoot conversation ID
		content: Message content
		result: API response from Chatwoot
	"""
	add_message_to_conversation(
		conversation_id=conversation_id,
		message_id=result.get("id"),
		content=content,
		message_type="outgoing",
		sender_type="agent",
		sender_name=frappe.session.user,
		created_at=result.get("created_at"),
	)


def cleanup_old_conversations():
	"""Clean up old conversations based on retention settings.

	This is called by the scheduler.
	"""
	settings = frappe.get_single("Chatwoot Settings")
	if not settings.enabled:
		return

	retention_days = settings.conversation_retention_days or 90
	if retention_days <= 0:
		return  # Keep forever

	cutoff_date = frappe.utils.add_days(now_datetime(), -retention_days)

	# Get old conversations
	old_conversations = frappe.get_all(
		"Chatwoot Conversation",
		filters={
			"status": "resolved",
			"updated_at": ["<", cutoff_date],
		},
		pluck="name",
	)

	for conv_name in old_conversations:
		try:
			frappe.delete_doc("Chatwoot Conversation", conv_name, ignore_permissions=True)
		except Exception as e:
			frappe.log_error(f"Failed to delete old conversation {conv_name}: {e}")

	if old_conversations:
		frappe.db.commit()


def _link_to_erpnext_contact(doc, chatwoot_contact_id, contact_data):
	"""Link conversation to existing ERPNext Customer by email.

	Only links if:
	- Email is provided in contact_data
	- A Customer with that email already exists in ERPNext

	Args:
		doc: Chatwoot Conversation document
		chatwoot_contact_id: Chatwoot contact ID
		contact_data: Contact data from Chatwoot
	"""
	chatwoot_contact_id = str(chatwoot_contact_id)

	# Check if already linked by Chatwoot ID
	customer = frappe.db.get_value(
		"Customer",
		{"chatwoot_contact_id": chatwoot_contact_id},
		"name"
	)
	if customer:
		doc.customer = customer
		return

	# Only proceed if email is provided
	email = contact_data.get("email")
	if not email:
		return

	# Find existing Customer by email using common function
	from erpnext_chatwoot_formbricks.common.contact_sync import find_erpnext_contact_by_email
	doctype, name = find_erpnext_contact_by_email(email)

	if doctype == "Customer" and name:
		doc.customer = name
		# Update the Customer with Chatwoot ID for future lookups
		frappe.db.set_value("Customer", name, "chatwoot_contact_id", chatwoot_contact_id)
		return

	# No matching Customer found - do nothing


def _parse_timestamp(timestamp):
	"""Parse timestamp from Chatwoot format.

	Handles various formats:
	- Unix timestamp (int/float)
	- ISO format with timezone: 2025-12-20 21:54:59.527000+00:00
	- Standard datetime string

	Args:
		timestamp: Timestamp string or Unix timestamp
	"""
	if not timestamp:
		return None

	try:
		if isinstance(timestamp, (int, float)):
			# Unix timestamp
			from datetime import datetime
			return datetime.fromtimestamp(timestamp)
		else:
			timestamp_str = str(timestamp)
			# Remove timezone info if present (e.g., +00:00, Z)
			# MariaDB doesn't accept timezone-aware datetime strings
			if '+' in timestamp_str:
				timestamp_str = timestamp_str.rsplit('+', 1)[0]
			elif timestamp_str.endswith('Z'):
				timestamp_str = timestamp_str[:-1]
			# Remove microseconds if too precise for the field
			if '.' in timestamp_str:
				parts = timestamp_str.split('.')
				if len(parts[1]) > 6:
					parts[1] = parts[1][:6]
				timestamp_str = '.'.join(parts)
			return get_datetime(timestamp_str)
	except Exception:
		return now_datetime()
