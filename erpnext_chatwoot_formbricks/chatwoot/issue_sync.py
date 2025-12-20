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

		api = ChatwootAPI(settings)

		# Extract text from HTML comment
		content = _extract_text_from_html(doc.content)

		if content:
			# Get the user's full name
			user_name = frappe.get_value("User", doc.owner, "full_name") or doc.owner

			# Format message with sender info
			message = f"[{user_name} via ERPNext]\n\n{content}"

			# Send to Chatwoot
			api.send_message(
				conversation_id=issue.chatwoot_conversation_id,
				content=message,
				message_type="outgoing",
				private=False
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
