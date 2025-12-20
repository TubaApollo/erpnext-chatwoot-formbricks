/**
 * ERPNext Chatwoot Formbricks Integration
 * Main JavaScript file
 */

frappe.provide("erpnext_chatwoot_formbricks");

erpnext_chatwoot_formbricks = {
	/**
	 * Open a Chatwoot conversation dialog
	 * @param {string} conversation_id - Chatwoot conversation ID
	 */
	open_conversation_dialog: function(conversation_id) {
		frappe.call({
			method: "erpnext_chatwoot_formbricks.chatwoot.api.get_conversation_messages",
			args: { conversation_id: conversation_id },
			callback: function(r) {
				if (r.message) {
					erpnext_chatwoot_formbricks.show_conversation_dialog(conversation_id, r.message);
				}
			}
		});
	},

	/**
	 * Show the conversation dialog
	 * @param {string} conversation_id - Chatwoot conversation ID
	 * @param {Object} messages_data - Messages data from API
	 */
	show_conversation_dialog: function(conversation_id, messages_data) {
		const messages = messages_data.payload || [];

		let messages_html = '<div class="chatwoot-messages" style="max-height: 400px; overflow-y: auto; padding: 10px;">';

		messages.forEach(function(msg) {
			const is_outgoing = msg.message_type === 'outgoing';
			const sender = msg.sender?.name || (is_outgoing ? 'Agent' : 'Contact');
			const time = frappe.datetime.str_to_user(msg.created_at);
			const bg_color = is_outgoing ? '#e3f2fd' : '#f5f5f5';
			const align = is_outgoing ? 'right' : 'left';

			messages_html += `
				<div style="margin-bottom: 10px; text-align: ${align};">
					<div style="display: inline-block; max-width: 70%; padding: 8px 12px; background: ${bg_color}; border-radius: 8px;">
						<div style="font-size: 11px; color: #666; margin-bottom: 4px;">${sender} - ${time}</div>
						<div>${msg.content || ''}</div>
					</div>
				</div>
			`;
		});

		messages_html += '</div>';

		const dialog = new frappe.ui.Dialog({
			title: __('Chatwoot Conversation'),
			size: 'large',
			fields: [
				{
					fieldtype: 'HTML',
					fieldname: 'messages_html',
					options: messages_html
				},
				{
					fieldtype: 'Section Break',
					label: __('Reply')
				},
				{
					fieldtype: 'Text',
					fieldname: 'reply_content',
					label: __('Message'),
					reqd: 1
				}
			],
			primary_action_label: __('Send Reply'),
			primary_action: function(values) {
				if (!values.reply_content) {
					frappe.msgprint(__('Please enter a message'));
					return;
				}

				frappe.call({
					method: "erpnext_chatwoot_formbricks.chatwoot.api.send_message_from_erpnext",
					args: {
						conversation_id: conversation_id,
						content: values.reply_content
					},
					callback: function(r) {
						if (r.message) {
							frappe.msgprint(__('Message sent successfully!'));
							dialog.hide();
						}
					}
				});
			},
			secondary_action_label: __('Open in Chatwoot'),
			secondary_action: function() {
				frappe.call({
					method: "frappe.client.get_single_value",
					args: {
						doctype: "Chatwoot Settings",
						field: "api_url"
					},
					callback: function(r) {
						if (r.message) {
							frappe.call({
								method: "frappe.client.get_single_value",
								args: {
									doctype: "Chatwoot Settings",
									field: "account_id"
								},
								callback: function(r2) {
									if (r2.message) {
										const url = `${r.message}/app/accounts/${r2.message}/conversations/${conversation_id}`;
										window.open(url, '_blank');
									}
								}
							});
						}
					}
				});
			}
		});

		dialog.show();
	},

	/**
	 * Show Chatwoot conversations for a Customer/Lead
	 * @param {string} doctype - Customer or Lead
	 * @param {string} docname - Document name
	 */
	show_conversations: function(doctype, docname) {
		const filters = {};
		if (doctype === 'Customer') {
			filters['customer'] = docname;
		} else if (doctype === 'Lead') {
			filters['lead'] = docname;
		}

		frappe.call({
			method: "frappe.client.get_list",
			args: {
				doctype: "Chatwoot Conversation",
				filters: filters,
				fields: ["name", "conversation_id", "status", "contact_name", "inbox_name", "updated_at"],
				order_by: "updated_at desc",
				limit_page_length: 10
			},
			callback: function(r) {
				if (r.message && r.message.length > 0) {
					erpnext_chatwoot_formbricks.show_conversations_list(r.message);
				} else {
					frappe.msgprint(__('No Chatwoot conversations found for this {0}', [doctype]));
				}
			}
		});
	},

	/**
	 * Show a list of conversations in a dialog
	 * @param {Array} conversations - List of conversation documents
	 */
	show_conversations_list: function(conversations) {
		let html = '<table class="table table-bordered">';
		html += '<thead><tr><th>Status</th><th>Contact</th><th>Inbox</th><th>Updated</th><th>Action</th></tr></thead>';
		html += '<tbody>';

		conversations.forEach(function(conv) {
			const status_color = conv.status === 'resolved' ? 'green' : (conv.status === 'open' ? 'orange' : 'grey');
			html += `<tr>
				<td><span class="indicator-pill ${status_color}">${conv.status}</span></td>
				<td>${conv.contact_name || '-'}</td>
				<td>${conv.inbox_name || '-'}</td>
				<td>${frappe.datetime.prettyDate(conv.updated_at)}</td>
				<td><button class="btn btn-xs btn-primary" onclick="erpnext_chatwoot_formbricks.open_conversation_dialog('${conv.conversation_id}')">${__('View')}</button></td>
			</tr>`;
		});

		html += '</tbody></table>';

		const dialog = new frappe.ui.Dialog({
			title: __('Chatwoot Conversations'),
			size: 'large',
			fields: [
				{
					fieldtype: 'HTML',
					fieldname: 'conversations_html',
					options: html
				}
			]
		});

		dialog.show();
	}
};
