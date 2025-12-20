"""Formbricks Settings DocType controller."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

from erpnext_chatwoot_formbricks.formbricks.api import FormbricksAPI


class FormbricksSettings(Document):
	"""Settings for Formbricks integration."""

	def validate(self):
		"""Validate settings before save."""
		if self.enabled:
			self._validate_api_credentials()

	def on_update(self):
		"""Handle settings update."""
		if self.enabled:
			self._register_webhook()

	def _validate_api_credentials(self):
		"""Validate API credentials by making a test request."""
		if not self.api_url or not self.api_key:
			return

		try:
			api = FormbricksAPI(self)
			api.test_connection()
		except Exception as e:
			frappe.throw(_("Failed to connect to Formbricks API: {0}").format(str(e)))

	def _register_webhook(self):
		"""Register webhook with Formbricks."""
		try:
			api = FormbricksAPI(self)
			webhook_url = self._get_webhook_url()

			result = api.register_webhook(
				url=webhook_url,
				triggers=["responseCreated", "responseUpdated", "responseFinished"]
			)

			if result:
				self.sync_status = "Webhook registered successfully"
				frappe.db.set_value("Formbricks Settings", None, "sync_status", "Webhook registered successfully")
		except Exception as e:
			self.sync_status = f"Webhook registration failed: {str(e)}"
			frappe.log_error(f"Formbricks webhook registration failed: {e}")

	def _get_webhook_url(self):
		"""Get the webhook URL for this ERPNext instance."""
		site_url = frappe.utils.get_url()
		return f"{site_url}/api/method/erpnext_chatwoot_formbricks.formbricks.webhook.handle"

	@frappe.whitelist()
	def test_connection(self):
		"""Test the Formbricks API connection."""
		try:
			api = FormbricksAPI(self)
			result = api.test_connection()
			if result:
				frappe.msgprint(_("Connection successful!"))
				return {"status": "success", "message": "Connection successful"}
			else:
				frappe.throw(_("Connection failed. Please check your credentials."))
		except Exception as e:
			frappe.throw(_("Connection failed: {0}").format(str(e)))

	@frappe.whitelist()
	def sync_surveys_manual(self):
		"""Manually sync surveys from Formbricks."""
		try:
			from erpnext_chatwoot_formbricks.formbricks.api import sync_surveys
			count = sync_surveys()
			self.last_sync = now_datetime()
			frappe.db.set_value("Formbricks Settings", None, "last_sync", self.last_sync)
			frappe.msgprint(_("Synced {0} surveys!").format(count))
		except Exception as e:
			frappe.throw(_("Survey sync failed: {0}").format(str(e)))


def get_formbricks_settings():
	"""Get Formbricks Settings singleton document."""
	return frappe.get_single("Formbricks Settings")


def is_formbricks_enabled():
	"""Check if Formbricks integration is enabled."""
	settings = get_formbricks_settings()
	return bool(settings.enabled)
