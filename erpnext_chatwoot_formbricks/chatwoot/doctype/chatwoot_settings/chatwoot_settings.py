"""Chatwoot Settings DocType controller."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

from erpnext_chatwoot_formbricks.chatwoot.api import ChatwootAPI


class ChatwootSettings(Document):
	"""Settings for Chatwoot integration."""

	def validate(self):
		"""Validate settings before save."""
		if self.enabled:
			self._validate_api_credentials()
			if self.auto_create_customer and self.auto_create_lead:
				frappe.throw(
					_("Cannot enable both 'Auto Create Customer' and 'Auto Create Lead'. Please choose one.")
				)

	def on_update(self):
		"""Handle settings update."""
		if self.enabled and not self.webhook_registered:
			self._register_webhook()
		elif not self.enabled and self.webhook_registered:
			self._unregister_webhook()

	def _validate_api_credentials(self):
		"""Validate API credentials by making a test request."""
		if not self.api_url or not self.api_access_token or not self.account_id:
			return

		try:
			api = ChatwootAPI(self)
			api.test_connection()
		except Exception as e:
			frappe.throw(_("Failed to connect to Chatwoot API: {0}").format(str(e)))

	def _register_webhook(self):
		"""Register webhook with Chatwoot."""
		try:
			api = ChatwootAPI(self)
			webhook_url = self._get_webhook_url()

			result = api.register_webhook(
				url=webhook_url,
				subscriptions=[
					"conversation_created",
					"conversation_updated",
					"conversation_status_changed",
					"message_created",
					"contact_created",
					"contact_updated",
				]
			)

			if result:
				self.webhook_registered = 1
				self.sync_status = "Webhook registered successfully"
				frappe.db.set_value("Chatwoot Settings", None, "webhook_registered", 1)
				frappe.db.set_value("Chatwoot Settings", None, "sync_status", "Webhook registered successfully")
		except Exception as e:
			self.sync_status = f"Webhook registration failed: {str(e)}"
			frappe.log_error(f"Chatwoot webhook registration failed: {e}")

	def _unregister_webhook(self):
		"""Unregister webhook from Chatwoot."""
		try:
			api = ChatwootAPI(self)
			api.unregister_webhook()
			self.webhook_registered = 0
			frappe.db.set_value("Chatwoot Settings", None, "webhook_registered", 0)
		except Exception as e:
			frappe.log_error(f"Chatwoot webhook unregistration failed: {e}")

	def _get_webhook_url(self):
		"""Get the webhook URL for this ERPNext instance."""
		site_url = frappe.utils.get_url()
		return f"{site_url}/api/method/erpnext_chatwoot_formbricks.chatwoot.webhook.handle"

	@frappe.whitelist()
	def test_connection(self):
		"""Test the Chatwoot API connection."""
		try:
			api = ChatwootAPI(self)
			result = api.test_connection()
			if result:
				frappe.msgprint(_("Connection successful!"))
				return {"status": "success", "message": "Connection successful"}
			else:
				frappe.throw(_("Connection failed. Please check your credentials."))
		except Exception as e:
			frappe.throw(_("Connection failed: {0}").format(str(e)))

	@frappe.whitelist()
	def sync_contacts(self):
		"""Manually sync contacts from Chatwoot."""
		try:
			from erpnext_chatwoot_formbricks.chatwoot.contact import sync_contacts_from_chatwoot
			sync_contacts_from_chatwoot()
			self.last_sync = now_datetime()
			frappe.db.set_value("Chatwoot Settings", None, "last_sync", self.last_sync)
			frappe.msgprint(_("Contact sync completed!"))
		except Exception as e:
			frappe.throw(_("Contact sync failed: {0}").format(str(e)))

	@frappe.whitelist()
	def register_webhook_manual(self):
		"""Manually register webhook with Chatwoot."""
		self._register_webhook()
		if self.webhook_registered:
			frappe.msgprint(_("Webhook registered successfully!"))
		else:
			frappe.throw(_("Webhook registration failed. Check error log for details."))


def get_chatwoot_settings():
	"""Get Chatwoot Settings singleton document."""
	return frappe.get_single("Chatwoot Settings")


def is_chatwoot_enabled():
	"""Check if Chatwoot integration is enabled."""
	settings = get_chatwoot_settings()
	return bool(settings.enabled)
