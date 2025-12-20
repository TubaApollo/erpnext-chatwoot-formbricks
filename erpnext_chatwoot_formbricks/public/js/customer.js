/**
 * Customer DocType customizations for Chatwoot integration
 */

frappe.ui.form.on('Customer', {
	refresh: function(frm) {
		if (!frm.is_new()) {
			// Add Chatwoot conversations button
			frm.add_custom_button(__('Chatwoot Conversations'), function() {
				erpnext_chatwoot_formbricks.show_conversations('Customer', frm.doc.name);
			}, __('Actions'));

			// Show indicator if customer has Chatwoot ID
			if (frm.doc.chatwoot_contact_id) {
				frm.dashboard.add_indicator(
					__('Linked to Chatwoot: {0}', [frm.doc.chatwoot_contact_id]),
					'blue'
				);
			}

			// Add quick action to start a new conversation
			frm.add_custom_button(__('Start Chat'), function() {
				erpnext_chatwoot_formbricks.start_new_conversation('Customer', frm.doc.name, frm.doc.chatwoot_contact_id);
			}, __('Chatwoot'));

			// Show Formbricks responses if any
			if (frm.doc.formbricks_contact_id) {
				frm.dashboard.add_indicator(
					__('Linked to Formbricks'),
					'green'
				);
			}
		}
	}
});

// Extend the erpnext_chatwoot_formbricks namespace
$.extend(erpnext_chatwoot_formbricks, {
	/**
	 * Start a new conversation with a contact
	 * @param {string} doctype - Customer or Lead
	 * @param {string} docname - Document name
	 * @param {string} contact_id - Chatwoot contact ID
	 */
	start_new_conversation: function(doctype, docname, contact_id) {
		if (!contact_id) {
			frappe.msgprint(__('This {0} is not linked to a Chatwoot contact yet.', [doctype]));
			return;
		}

		const dialog = new frappe.ui.Dialog({
			title: __('Start New Conversation'),
			fields: [
				{
					fieldtype: 'Text',
					fieldname: 'message',
					label: __('Initial Message'),
					reqd: 1
				}
			],
			primary_action_label: __('Start Conversation'),
			primary_action: function(values) {
				frappe.call({
					method: "erpnext_chatwoot_formbricks.chatwoot.api.create_conversation",
					args: {
						contact_id: contact_id,
						message: values.message
					},
					callback: function(r) {
						if (r.message) {
							frappe.msgprint(__('Conversation started successfully!'));
							dialog.hide();
						}
					}
				});
			}
		});

		dialog.show();
	}
});
