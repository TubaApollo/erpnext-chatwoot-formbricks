"""Formbricks API client for interacting with Formbricks server."""

import frappe
import requests
from frappe import _
from frappe.utils import now_datetime


class FormbricksAPI:
	"""API client for Formbricks."""

	def __init__(self, settings=None):
		"""Initialize with settings."""
		if settings is None:
			settings = frappe.get_single("Formbricks Settings")

		self.api_url = settings.api_url.rstrip("/")
		self.environment_id = settings.environment_id
		self.api_key = settings.get_password("api_key")
		self.timeout = 30

	def _get_headers(self):
		"""Get headers for API requests."""
		return {
			"x-api-key": self.api_key,
			"Content-Type": "application/json",
		}

	def _make_request(self, method, endpoint, data=None, params=None):
		"""Make a request to the Formbricks API."""
		url = f"{self.api_url}/api/v1/{endpoint}"

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
		except requests.exceptions.HTTPError as e:
			# Log the actual response body for debugging
			error_body = ""
			try:
				error_body = e.response.text
			except:
				pass
			frappe.log_error(
				f"Formbricks API request failed: {method} {url}\n"
				f"Status: {e.response.status_code}\n"
				f"Request data: {data}\n"
				f"Response body: {error_body}",
				"Formbricks API Error"
			)
			raise
		except requests.exceptions.RequestException as e:
			frappe.log_error(
				f"Formbricks API request failed: {method} {url} - {str(e)}",
				"Formbricks API Error"
			)
			raise

	def test_connection(self):
		"""Test the API connection by fetching environment info."""
		try:
			# Try to get surveys as a connection test
			response = self._make_request("GET", f"management/surveys")
			return True
		except Exception as e:
			frappe.log_error(f"Formbricks connection test failed: {e}")
			return False

	# ==========================================================================
	# Webhook Management
	# ==========================================================================

	def register_webhook(self, url, triggers, survey_ids=None):
		"""Register a webhook with Formbricks.

		Args:
			url: Webhook URL to call
			triggers: List of triggers (e.g., ["responseCreated", "responseFinished"])
			survey_ids: Optional list of survey IDs to limit webhook to specific surveys.
			           If empty or None, webhook listens to all surveys.
		"""
		data = {
			"url": url,
			"triggers": triggers,
			"surveyIds": survey_ids if survey_ids else [],  # Required field, empty = all surveys
		}
		return self._make_request("POST", "webhooks", data=data)

	def get_webhooks(self):
		"""Get list of registered webhooks."""
		return self._make_request("GET", "webhooks")

	def delete_webhook(self, webhook_id):
		"""Delete a webhook."""
		return self._make_request("DELETE", f"webhooks/{webhook_id}")

	# ==========================================================================
	# Survey Management
	# ==========================================================================

	def get_surveys(self, limit=100, offset=0):
		"""Get list of surveys."""
		params = {"limit": limit, "offset": offset}
		return self._make_request("GET", "management/surveys", params=params)

	def get_survey(self, survey_id):
		"""Get a specific survey."""
		return self._make_request("GET", f"management/surveys/{survey_id}")

	# ==========================================================================
	# Response Management
	# ==========================================================================

	def get_responses(self, survey_id, limit=100, offset=0):
		"""Get responses for a survey."""
		params = {"limit": limit, "offset": offset}
		return self._make_request("GET", f"management/surveys/{survey_id}/responses", params=params)

	def get_response(self, response_id):
		"""Get a specific response."""
		return self._make_request("GET", f"management/responses/{response_id}")

	# ==========================================================================
	# Contact/Person Management
	# ==========================================================================

	def get_contacts(self, limit=100, offset=0):
		"""Get list of contacts/persons."""
		params = {"limit": limit, "offset": offset}
		return self._make_request("GET", "management/contacts", params=params)

	def get_contact(self, contact_id):
		"""Get a specific contact."""
		return self._make_request("GET", f"management/contacts/{contact_id}")


def sync_surveys():
	"""Sync surveys from Formbricks to ERPNext.

	Returns:
		int: Number of surveys synced
	"""
	settings = frappe.get_single("Formbricks Settings")
	if not settings.enabled:
		return 0

	api = FormbricksAPI(settings)
	count = 0

	try:
		response = api.get_surveys()
		surveys = response.get("data", [])

		for survey in surveys:
			try:
				_sync_survey(survey)
				count += 1
			except Exception as e:
				frappe.log_error(f"Error syncing survey {survey.get('id')}: {e}")

		# Update last sync time
		frappe.db.set_value("Formbricks Settings", None, "last_sync", now_datetime())
		frappe.db.commit()

	except Exception as e:
		frappe.log_error(f"Error fetching surveys from Formbricks: {e}")

	return count


def _sync_survey(survey_data):
	"""Sync a single survey from Formbricks.

	Args:
		survey_data: Survey data from Formbricks API
	"""
	survey_id = survey_data.get("id")
	if not survey_id:
		return

	# Check if survey exists
	existing = frappe.db.exists("Formbricks Survey", {"survey_id": survey_id})

	if existing:
		doc = frappe.get_doc("Formbricks Survey", existing)
	else:
		doc = frappe.new_doc("Formbricks Survey")
		doc.survey_id = survey_id

	# Update fields
	doc.name_field = survey_data.get("name", "Unnamed Survey")
	doc.status = survey_data.get("status", "draft")
	doc.survey_type = survey_data.get("type", "link")

	# Store questions as JSON
	import json
	questions = survey_data.get("questions", [])
	doc.questions_json = json.dumps(questions)

	doc.save(ignore_permissions=True)
	frappe.db.commit()
