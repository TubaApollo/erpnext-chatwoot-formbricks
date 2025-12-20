"""Chatwoot API client for interacting with Chatwoot server."""

import frappe
import requests
from frappe import _


class ChatwootAPI:
	"""API client for Chatwoot."""

	def __init__(self, settings=None, api_token=None):
		"""Initialize with settings.

		Args:
			settings: Chatwoot Settings document (optional, will fetch if not provided)
			api_token: Override API token (optional, for per-user tokens)
		"""
		if settings is None:
			settings = frappe.get_single("Chatwoot Settings")

		self.api_url = settings.api_url.rstrip("/")
		self.account_id = settings.account_id
		# Use provided token or fall back to global settings
		self.api_token = api_token or settings.get_password("api_access_token")
		self.timeout = 30

	def _get_headers(self):
		"""Get headers for API requests."""
		return {
			"api_access_token": self.api_token,
			"Content-Type": "application/json",
		}

	def _make_request(self, method, endpoint, data=None, params=None):
		"""Make a request to the Chatwoot API."""
		url = f"{self.api_url}/api/v1/accounts/{self.account_id}/{endpoint}"

		try:
			response = requests.request(
				method=method,
				url=url,
				headers=self._get_headers(),
				json=data,
				params=params,
				timeout=self.timeout,
			)
			response.raise_for_status()
			return response.json() if response.content else {}
		except requests.exceptions.RequestException as e:
			frappe.log_error(
				f"Chatwoot API request failed: {method} {url} - {str(e)}",
				"Chatwoot API Error"
			)
			raise

	def test_connection(self):
		"""Test the API connection by fetching account info."""
		try:
			url = f"{self.api_url}/api/v1/accounts/{self.account_id}"
			response = requests.get(
				url,
				headers=self._get_headers(),
				timeout=self.timeout,
			)
			response.raise_for_status()
			return True
		except Exception as e:
			frappe.log_error(f"Chatwoot connection test failed: {e}")
			return False

	# ==========================================================================
	# Webhook Management
	# ==========================================================================

	def register_webhook(self, url, subscriptions):
		"""Register a webhook with Chatwoot."""
		data = {
			"url": url,
			"subscriptions": subscriptions,
		}
		return self._make_request("POST", "webhooks", data=data)

	def unregister_webhook(self):
		"""Unregister webhook from Chatwoot."""
		# Get existing webhooks
		webhooks = self._make_request("GET", "webhooks")
		site_url = frappe.utils.get_url()

		for webhook in webhooks.get("payload", []):
			if site_url in webhook.get("url", ""):
				self._make_request("DELETE", f"webhooks/{webhook['id']}")
				return True
		return False

	def get_webhooks(self):
		"""Get list of registered webhooks."""
		return self._make_request("GET", "webhooks")

	# ==========================================================================
	# Contact Management
	# ==========================================================================

	def get_contacts(self, page=1, sort="name"):
		"""Get list of contacts."""
		params = {"page": page, "sort": sort}
		return self._make_request("GET", "contacts", params=params)

	def get_contact(self, contact_id):
		"""Get a specific contact."""
		return self._make_request("GET", f"contacts/{contact_id}")

	def create_contact(self, name, email=None, phone=None, identifier=None, custom_attributes=None):
		"""Create a new contact."""
		data = {"name": name}
		if email:
			data["email"] = email
		if phone:
			data["phone_number"] = phone
		if identifier:
			data["identifier"] = identifier
		if custom_attributes:
			data["custom_attributes"] = custom_attributes

		return self._make_request("POST", "contacts", data=data)

	def update_contact(self, contact_id, **kwargs):
		"""Update a contact."""
		return self._make_request("PUT", f"contacts/{contact_id}", data=kwargs)

	def search_contacts(self, query):
		"""Search for contacts."""
		params = {"q": query}
		return self._make_request("GET", "contacts/search", params=params)

	# ==========================================================================
	# Conversation Management
	# ==========================================================================

	def get_conversations(self, status="open", page=1):
		"""Get list of conversations."""
		params = {"status": status, "page": page}
		return self._make_request("GET", "conversations", params=params)

	def get_conversation(self, conversation_id):
		"""Get a specific conversation."""
		return self._make_request("GET", f"conversations/{conversation_id}")

	def get_conversation_messages(self, conversation_id):
		"""Get messages for a conversation."""
		return self._make_request("GET", f"conversations/{conversation_id}/messages")

	def update_conversation_status(self, conversation_id, status):
		"""Update conversation status (open, resolved, pending)."""
		data = {"status": status}
		return self._make_request("POST", f"conversations/{conversation_id}/toggle_status", data=data)

	def assign_conversation(self, conversation_id, assignee_id=None, team_id=None):
		"""Assign conversation to an agent or team."""
		data = {}
		if assignee_id:
			data["assignee_id"] = assignee_id
		if team_id:
			data["team_id"] = team_id
		return self._make_request("POST", f"conversations/{conversation_id}/assignments", data=data)

	# ==========================================================================
	# Message Management
	# ==========================================================================

	def send_message(self, conversation_id, content, message_type="outgoing", private=False):
		"""Send a message to a conversation."""
		data = {
			"content": content,
			"message_type": message_type,
			"private": private,
		}
		return self._make_request("POST", f"conversations/{conversation_id}/messages", data=data)

	def create_conversation(self, contact_id, inbox_id, message=None):
		"""Create a new conversation with a contact."""
		data = {
			"contact_id": contact_id,
			"inbox_id": inbox_id,
		}
		if message:
			data["message"] = {"content": message}

		return self._make_request("POST", "conversations", data=data)

	# ==========================================================================
	# Inbox Management
	# ==========================================================================

	def get_inboxes(self):
		"""Get list of inboxes."""
		return self._make_request("GET", "inboxes")

	def get_inbox(self, inbox_id):
		"""Get a specific inbox."""
		return self._make_request("GET", f"inboxes/{inbox_id}")

	# ==========================================================================
	# Agent/Team Management
	# ==========================================================================

	def get_agents(self):
		"""Get list of agents."""
		return self._make_request("GET", "agents")

	def get_teams(self):
		"""Get list of teams."""
		return self._make_request("GET", "teams")

	# ==========================================================================
	# Labels
	# ==========================================================================

	def get_labels(self):
		"""Get list of labels."""
		return self._make_request("GET", "labels")

	def add_conversation_labels(self, conversation_id, labels):
		"""Add labels to a conversation."""
		data = {"labels": labels}
		return self._make_request("POST", f"conversations/{conversation_id}/labels", data=data)


@frappe.whitelist()
def send_message_from_erpnext(conversation_id, content):
	"""Send a message from ERPNext to Chatwoot conversation.

	This function is exposed as a whitelisted API for use from ERPNext UI.
	"""
	settings = frappe.get_single("Chatwoot Settings")
	if not settings.enabled:
		frappe.throw(_("Chatwoot integration is not enabled"))

	api = ChatwootAPI(settings)
	result = api.send_message(conversation_id, content)

	# Log the message in ERPNext
	if result:
		from erpnext_chatwoot_formbricks.chatwoot.conversation import log_outgoing_message
		log_outgoing_message(conversation_id, content, result)

	return result


@frappe.whitelist()
def get_conversation_messages(conversation_id):
	"""Get messages for a Chatwoot conversation.

	This function is exposed as a whitelisted API for use from ERPNext UI.
	"""
	settings = frappe.get_single("Chatwoot Settings")
	if not settings.enabled:
		frappe.throw(_("Chatwoot integration is not enabled"))

	api = ChatwootAPI(settings)
	return api.get_conversation_messages(conversation_id)


@frappe.whitelist()
def update_conversation_status(conversation_id, status):
	"""Update Chatwoot conversation status from ERPNext.

	Args:
		conversation_id: Chatwoot conversation ID
		status: New status (open, resolved, pending)
	"""
	settings = frappe.get_single("Chatwoot Settings")
	if not settings.enabled:
		frappe.throw(_("Chatwoot integration is not enabled"))

	api = ChatwootAPI(settings)
	return api.update_conversation_status(conversation_id, status)
