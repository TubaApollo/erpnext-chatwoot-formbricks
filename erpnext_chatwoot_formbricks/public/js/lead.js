/**
 * Lead DocType customizations for Chatwoot and Formbricks integration
 */

frappe.ui.form.on('Lead', {
	refresh: function(frm) {
		if (!frm.is_new()) {
			// Add Chatwoot conversations button
			frm.add_custom_button(__('Chatwoot Conversations'), function() {
				erpnext_chatwoot_formbricks.show_conversations('Lead', frm.doc.name);
			}, __('Actions'));

			// Show indicator if lead has Chatwoot ID
			if (frm.doc.chatwoot_contact_id) {
				frm.dashboard.add_indicator(
					__('Linked to Chatwoot'),
					'blue'
				);
			}

			// Show indicator if lead has conversation
			if (frm.doc.chatwoot_conversation_id) {
				frm.add_custom_button(__('View Conversation'), function() {
					erpnext_chatwoot_formbricks.open_conversation_dialog(frm.doc.chatwoot_conversation_id);
				}, __('Chatwoot'));
			}

			// Show Formbricks response if linked
			if (frm.doc.formbricks_response_id) {
				frm.dashboard.add_indicator(
					__('From Survey Response'),
					'green'
				);

				frm.add_custom_button(__('View Survey Response'), function() {
					erpnext_chatwoot_formbricks.show_formbricks_response(frm.doc.formbricks_response_id);
				}, __('Formbricks'));
			}

			// Add convert to customer button with integration data transfer
			if (frm.doc.status !== 'Converted') {
				frm.add_custom_button(__('Convert with Integrations'), function() {
					erpnext_chatwoot_formbricks.convert_lead_with_integrations(frm.doc.name);
				}, __('Actions'));
			}
		}
	}
});

// Extend the erpnext_chatwoot_formbricks namespace
$.extend(erpnext_chatwoot_formbricks, {
	/**
	 * Show a Formbricks response
	 * @param {string} response_id - Formbricks response ID
	 */
	show_formbricks_response: function(response_id) {
		frappe.call({
			method: "frappe.client.get",
			args: {
				doctype: "Formbricks Response",
				filters: { response_id: response_id }
			},
			callback: function(r) {
				if (r.message) {
					const response = r.message;
					let data = {};
					try {
						data = JSON.parse(response.data_json || '{}');
					} catch (e) {}

					let html = '<div class="formbricks-response">';
					html += `<p><strong>${__('Survey')}:</strong> ${response.survey || '-'}</p>`;
					html += `<p><strong>${__('Status')}:</strong> ${response.finished ? 'Completed' : 'In Progress'}</p>`;
					html += `<p><strong>${__('Created')}:</strong> ${frappe.datetime.str_to_user(response.created_at)}</p>`;

					if (Object.keys(data).length > 0) {
						html += `<hr><h5>${__('Response Data')}</h5>`;
						html += '<table class="table table-bordered">';
						for (const [key, value] of Object.entries(data)) {
							html += `<tr><td><strong>${key}</strong></td><td>${value || '-'}</td></tr>`;
						}
						html += '</table>';
					}

					html += '</div>';

					const dialog = new frappe.ui.Dialog({
						title: __('Formbricks Response'),
						fields: [
							{
								fieldtype: 'HTML',
								fieldname: 'response_html',
								options: html
							}
						]
					});

					dialog.show();
				} else {
					frappe.msgprint(__('Response not found'));
				}
			}
		});
	},

	/**
	 * Convert lead to customer with integration data transfer
	 * @param {string} lead_name - Lead document name
	 */
	convert_lead_with_integrations: function(lead_name) {
		frappe.confirm(
			__('This will convert the Lead to a Customer and transfer all integration IDs (Chatwoot, Formbricks). Continue?'),
			function() {
				frappe.call({
					method: "erpnext_chatwoot_formbricks.common.lead_creation.convert_lead_to_customer",
					args: { lead_name: lead_name },
					callback: function(r) {
						if (r.message) {
							frappe.msgprint(__('Lead converted to Customer: {0}', [r.message]));
							frappe.set_route('Form', 'Customer', r.message);
						}
					}
				});
			}
		);
	}
});
