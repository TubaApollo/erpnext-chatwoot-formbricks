"""Issue to Chatwoot synchronization utilities."""

import frappe
from frappe import _


def send_comment_to_chatwoot(doc, method=None):
	"""Send Issue comment to Chatwoot as a message.

	This is called via doc_events hook when a Comment is inserted.

	Args:
		doc: Comment document
		method: Event method (after_insert)
	"""
	# Only process comments on Issues
	if doc.reference_doctype != "Issue":
		return

	# Only process actual comments (not system comments)
	if doc.comment_type != "Comment":
		return

	# Get the Issue
	issue = frappe.get_doc("Issue", doc.reference_name)

	# Check if Issue has a Chatwoot conversation ID
	if not issue.chatwoot_conversation_id:
		return

	# Check if Chatwoot is enabled
	settings = frappe.get_single("Chatwoot Settings")
	if not settings.enabled:
		return

	# Don't send messages that came FROM Chatwoot (avoid loop)
	# Check if the comment was created by the webhook (contains our formatting)
	if "<strong>🤖" in doc.content or "<strong>👤" in doc.content or "<strong>💬" in doc.content:
		return

	try:
		from erpnext_chatwoot_formbricks.chatwoot.api import ChatwootAPI

		# Get user-specific Chatwoot API token (if configured)
		user_token = None
		user_doc = frappe.get_doc("User", doc.owner)
		if hasattr(user_doc, "chatwoot_api_token") and user_doc.chatwoot_api_token:
			user_token = user_doc.get_password("chatwoot_api_token")

		# Use user token if available, otherwise global token
		api = ChatwootAPI(settings, api_token=user_token)

		# Extract text from HTML comment
		content = _extract_text_from_html(doc.content)

		if content:
			# Send to Chatwoot (agent name is shown automatically by Chatwoot)
			api.send_message(
				conversation_id=issue.chatwoot_conversation_id,
				content=content,
				message_type="outgoing",
				private=False
			)

			# Set conversation status to "open" when agent replies from ERPNext
			api.update_conversation_status(
				conversation_id=issue.chatwoot_conversation_id,
				status="open"
			)

	except Exception as e:
		frappe.log_error(
			f"Error sending Issue comment to Chatwoot: {e}",
			"Chatwoot Issue Sync Error"
		)


def _extract_text_from_html(html_content):
	"""Extract plain text from HTML content.

	Args:
		html_content: HTML string

	Returns:
		Plain text string
	"""
	if not html_content:
		return ""

	try:
		from bs4 import BeautifulSoup
		soup = BeautifulSoup(html_content, "html.parser")
		return soup.get_text(separator="\n").strip()
	except ImportError:
		# Fallback: simple HTML tag removal
		import re
		text = re.sub(r'<[^>]+>', '', html_content)
		return text.strip()
