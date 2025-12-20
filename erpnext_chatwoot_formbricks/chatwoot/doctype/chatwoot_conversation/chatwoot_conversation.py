"""Chatwoot Conversation DocType controller."""

import frappe
from frappe import _
from frappe.model.document import Document

from erpnext_chatwoot_formbricks.chatwoot.api import ChatwootAPI


class ChatwootConversation(Document):
	"""Controller for Chatwoot Conversation document."""

	def before_save(self):
		"""Update timestamps before save."""
		if not self.created_at:
			self.created_at = frappe.utils.now_datetime()
		self.updated_at = frappe.utils.now_datetime()

	@frappe.whitelist()
	def send_reply(self, content):
		"""Send a reply to this conversation.

		Args:
			content: Message content to send
		"""
		settings = frappe.get_single("Chatwoot Settings")
		if not settings.enabled:
			frappe.throw(_("Chatwoot integration is not enabled"))

		api = ChatwootAPI(settings)
		result = api.send_message(self.conversation_id, content)

		if result:
			# Add message to local record
			self.append("messages", {
				"message_id": result.get("id"),
				"content": content,
				"message_type": "outgoing",
				"sender_type": "agent",
				"sender_name": frappe.session.user,
				"created_at": frappe.utils.now_datetime(),
			})
			self.save()
			frappe.msgprint(_("Message sent successfully!"))

		return result

	@frappe.whitelist()
	def update_status(self, status):
		"""Update the conversation status in Chatwoot.

		Args:
			status: New status (open, resolved, pending)
		"""
		settings = frappe.get_single("Chatwoot Settings")
		if not settings.enabled:
			frappe.throw(_("Chatwoot integration is not enabled"))

		api = ChatwootAPI(settings)
		result = api.update_conversation_status(self.conversation_id, status)

		if result:
			self.status = status
			self.save()
			frappe.msgprint(_("Status updated to {0}").format(status))

		return result

	@frappe.whitelist()
	def refresh_messages(self):
		"""Refresh messages from Chatwoot."""
		settings = frappe.get_single("Chatwoot Settings")
		if not settings.enabled:
			frappe.throw(_("Chatwoot integration is not enabled"))

		api = ChatwootAPI(settings)
		messages_data = api.get_conversation_messages(self.conversation_id)

		if messages_data:
			self._sync_messages(messages_data.get("payload", []))
			self.save()
			frappe.msgprint(_("Messages refreshed!"))

		return messages_data

	def _sync_messages(self, messages):
		"""Sync messages from Chatwoot API response.

		Args:
			messages: List of message objects from Chatwoot
		"""
		existing_ids = {m.message_id for m in self.messages}

		for msg in messages:
			msg_id = str(msg.get("id"))
			if msg_id not in existing_ids:
				sender = msg.get("sender", {})
				self.append("messages", {
					"message_id": msg_id,
					"content": msg.get("content", ""),
					"message_type": msg.get("message_type", "incoming"),
					"sender_type": sender.get("type", "contact"),
					"sender_id": sender.get("id"),
					"sender_name": sender.get("name"),
					"created_at": msg.get("created_at"),
				})

	@frappe.whitelist()
	def open_in_chatwoot(self):
		"""Get URL to open this conversation in Chatwoot."""
		settings = frappe.get_single("Chatwoot Settings")
		if not settings.api_url:
			frappe.throw(_("Chatwoot API URL not configured"))

		url = f"{settings.api_url}/app/accounts/{settings.account_id}/conversations/{self.conversation_id}"
		return {"url": url}
