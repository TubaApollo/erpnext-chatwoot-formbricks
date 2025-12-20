"""Common utilities shared between integrations."""

import frappe
from frappe.utils import get_datetime, now_datetime


def parse_timestamp(timestamp):
	"""Parse timestamp from various formats.

	Args:
		timestamp: Timestamp string, Unix timestamp, or datetime

	Returns:
		datetime object
	"""
	if not timestamp:
		return None

	try:
		if isinstance(timestamp, (int, float)):
			# Unix timestamp
			from datetime import datetime
			return datetime.fromtimestamp(timestamp)
		else:
			return get_datetime(timestamp)
	except Exception:
		return now_datetime()


def get_site_url():
	"""Get the current site URL."""
	return frappe.utils.get_url()


def log_integration_error(integration, message, title=None):
	"""Log an integration error.

	Args:
		integration: Integration name (chatwoot, formbricks)
		message: Error message
		title: Optional title
	"""
	frappe.log_error(
		message=message,
		title=title or f"{integration.title()} Integration Error"
	)


def get_integration_settings(integration):
	"""Get settings for an integration.

	Args:
		integration: Integration name (chatwoot, formbricks)

	Returns:
		Settings document
	"""
	doctype_map = {
		"chatwoot": "Chatwoot Settings",
		"formbricks": "Formbricks Settings",
	}

	doctype = doctype_map.get(integration.lower())
	if not doctype:
		raise ValueError(f"Unknown integration: {integration}")

	return frappe.get_single(doctype)


def is_integration_enabled(integration):
	"""Check if an integration is enabled.

	Args:
		integration: Integration name (chatwoot, formbricks)

	Returns:
		bool
	"""
	try:
		settings = get_integration_settings(integration)
		return bool(settings.enabled)
	except Exception:
		return False
