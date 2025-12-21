"""Formbricks Response DocType controller."""

import json
import frappe
from frappe.model.document import Document


# Mapping of Formbricks field name patterns to human-readable labels
FIELD_LABELS = {
	"contactinfo": "Contact Information",
	"projectdesc": "Project Description",
	"timeline": "Timeline",
	"projecttype": "Project Type",
	"budget": "Budget",
	"company": "Company",
	"email": "Email",
	"phone": "Phone",
	"name": "Name",
	"message": "Message",
	"feedback": "Feedback",
	"rating": "Rating",
	"comment": "Comment",
	"notes": "Notes",
	"requirements": "Requirements",
	"priority": "Priority",
	"deadline": "Deadline",
	"industry": "Industry",
	"size": "Size",
	"website": "Website",
	"referral": "Referral",
	"source": "Source",
}

# Mapping of Formbricks option values to human-readable labels
VALUE_LABELS = {
	"asap000000001": "ASAP",
	"asap": "ASAP",
	"months13aaaaa": "1-3 Months",
	"months36aaaaa": "3-6 Months",
	"months6plus": "6+ Months",
	"betriebseinr01": "Betriebseinrichtung",
	"webdesign": "Web Design",
	"development": "Development",
	"consulting": "Consulting",
	"support": "Support",
	"other": "Other",
}


class FormbricksResponse(Document):
	"""Controller for Formbricks Response document."""

	def onload(self):
		"""Set formatted data on load."""
		self.set("formatted_data", self.get_formatted_html())

	def get_formatted_html(self):
		"""Generate formatted HTML from response data."""
		if not self.data_json:
			return "<p><em>No response data</em></p>"

		try:
			data = json.loads(self.data_json)
		except (json.JSONDecodeError, TypeError):
			return "<p><em>Invalid JSON data</em></p>"

		if not data:
			return "<p><em>Empty response</em></p>"

		html = ['<table class="table table-bordered" style="width: 100%;">']
		html.append('<thead><tr><th style="width: 30%;">Field</th><th>Value</th></tr></thead>')
		html.append('<tbody>')

		for field_key, value in data.items():
			label = self._get_field_label(field_key)
			formatted_value = self._format_value(value, field_key)
			html.append(f'<tr><td><strong>{label}</strong></td><td>{formatted_value}</td></tr>')

		html.append('</tbody></table>')
		return '\n'.join(html)

	def _get_field_label(self, field_key):
		"""Convert Formbricks field key to human-readable label."""
		# Remove trailing random characters (e.g., "contactinfo01ab" -> "contactinfo")
		clean_key = ''.join(c for c in field_key if c.isalpha()).lower()

		# Look for matching pattern in FIELD_LABELS
		for pattern, label in FIELD_LABELS.items():
			if pattern in clean_key:
				return label

		# Fallback: capitalize and add spaces
		return field_key.replace('_', ' ').replace('-', ' ').title()

	def _format_value(self, value, field_key=None):
		"""Format a value for display."""
		if value is None:
			return '<em>-</em>'

		if isinstance(value, list):
			# Handle contact info arrays
			if 'contact' in (field_key or '').lower():
				# Typical format: [firstname, lastname, email, phone, company]
				labels = ['First Name', 'Last Name', 'Email', 'Phone', 'Company']
				parts = []
				for i, v in enumerate(value):
					if v:
						label = labels[i] if i < len(labels) else f'Field {i+1}'
						parts.append(f'<strong>{label}:</strong> {frappe.utils.escape_html(str(v))}')
				return '<br>'.join(parts) if parts else '<em>-</em>'
			else:
				# Generic list
				formatted = [self._format_single_value(v) for v in value if v]
				return ', '.join(formatted) if formatted else '<em>-</em>'

		return self._format_single_value(value)

	def _format_single_value(self, value):
		"""Format a single value."""
		if value is None or value == '':
			return '<em>-</em>'

		str_val = str(value)

		# Check if it's a known value that needs translation
		lower_val = str_val.lower()
		if lower_val in VALUE_LABELS:
			return VALUE_LABELS[lower_val]

		# Check for partial matches in value labels
		for pattern, label in VALUE_LABELS.items():
			if pattern in lower_val:
				return label

		# Escape HTML and return
		return frappe.utils.escape_html(str_val)
