# ERPNext Chatwoot Formbricks Integration

A Frappe/ERPNext v15 plugin for bidirectional integration with **Chatwoot** (customer support) and **Formbricks** (surveys & feedback).

## Features

### Chatwoot Integration
- **Contact Sync**: Bidirectional synchronization of contacts between Chatwoot and ERPNext (Customer/Lead)
- **Conversation Tracking**: View and manage Chatwoot conversations directly in ERPNext
- **Reply from ERPNext**: Send messages to Chatwoot conversations without leaving ERPNext
- **Webhook Support**: Real-time updates via Chatwoot webhooks
- **Issue Creation**: Optionally create ERPNext Issues from Chatwoot conversations

### Formbricks Integration
- **Survey Sync**: Sync survey definitions from Formbricks
- **Response Tracking**: Store and analyze survey responses in ERPNext
- **Lead Generation**: Automatically create Leads from survey responses
- **Contact Linking**: Link survey responses to existing Customers or Leads

### Common Features
- **Lead Scoring**: Score leads based on survey responses and conversation data
- **Lead Conversion**: Convert leads to customers with integration data preserved
- **Custom Fields**: Automatic creation of custom fields for integration IDs

## Requirements

- Frappe Framework v15+
- ERPNext v15+
- Python 3.10+
- Chatwoot (self-hosted or cloud)
- Formbricks (self-hosted or cloud)

## Installation

### Using Bench

```bash
# Get the app
bench get-app https://github.com/TubaApollo/erpnext-chatwoot-formbricks.git

# Install on your site
bench --site your-site.local install-app erpnext_chatwoot_formbricks

# Run migrations
bench --site your-site.local migrate

# Clear cache
bench --site your-site.local clear-cache
```

### Docker Installation

If using Frappe Docker, add the app to your `apps.json`:

```json
[
  {
    "url": "https://github.com/TubaApollo/erpnext-chatwoot-formbricks.git",
    "branch": "main"
  }
]
```

Then rebuild your containers.

## Configuration

### Chatwoot Settings

1. Go to **Chatwoot Settings** in ERPNext
2. Enable the integration
3. Enter your Chatwoot API URL (e.g., `https://chatwoot.example.com`)
4. Enter your Account ID
5. Enter your API Access Token (from Chatwoot > Settings > Access Token)
6. Configure sync options:
   - Auto Create Customer/Lead
   - Default Inbox ID
   - Customer Group

### Formbricks Settings

1. Go to **Formbricks Settings** in ERPNext
2. Enable the integration
3. Enter your Formbricks API URL (e.g., `https://formbricks.example.com`)
4. Enter your Environment ID
5. Enter your API Key (from Formbricks > Settings > API Keys)
6. Configure lead creation settings

### Webhook Configuration

#### Chatwoot Webhook

In Chatwoot, go to **Settings > Integrations > Webhooks** and add:

- **URL**: `https://your-erpnext.com/api/method/erpnext_chatwoot_formbricks.chatwoot.webhook.handle`
- **Events**: conversation_created, conversation_updated, message_created, contact_created, contact_updated

#### Formbricks Webhook

In Formbricks, go to **Configuration > Integrations > Webhooks** and add:

- **URL**: `https://your-erpnext.com/api/method/erpnext_chatwoot_formbricks.formbricks.webhook.handle`
- **Triggers**: responseCreated, responseUpdated, responseFinished

## Usage

### Viewing Chatwoot Conversations

1. Open a Customer or Lead document
2. Click **Actions > Chatwoot Conversations** to see linked conversations
3. Click **View** on any conversation to see messages and reply

### Replying to Conversations

1. Open the conversation dialog
2. Type your message in the Reply field
3. Click **Send Reply**

### Survey Responses

1. Go to **Formbricks Response** list to view all responses
2. Click on a response to see details
3. Linked leads will show the response in their form

### Lead Conversion

When converting a Lead to Customer, all integration IDs (Chatwoot contact ID, Formbricks IDs) are transferred automatically.

## DocTypes

### Chatwoot Settings
Single DocType for Chatwoot configuration.

### Chatwoot Conversation
Stores conversations from Chatwoot with linked messages.

### Chatwoot Message
Child table for conversation messages.

### Formbricks Settings
Single DocType for Formbricks configuration.

### Formbricks Survey
Stores survey definitions synced from Formbricks.

### Formbricks Response
Stores survey responses with linked Customer/Lead.

## API Endpoints

### Chatwoot

```python
# Send message from ERPNext
frappe.call({
    method: "erpnext_chatwoot_formbricks.chatwoot.api.send_message_from_erpnext",
    args: {
        conversation_id: "123",
        content: "Hello from ERPNext!"
    }
});

# Get conversation messages
frappe.call({
    method: "erpnext_chatwoot_formbricks.chatwoot.api.get_conversation_messages",
    args: {
        conversation_id: "123"
    }
});
```

### Lead Conversion

```python
# Convert lead with integration data
frappe.call({
    method: "erpnext_chatwoot_formbricks.common.lead_creation.convert_lead_to_customer",
    args: {
        lead_name: "LEAD-00001"
    }
});
```

## Custom Fields

The app automatically creates these custom fields:

### Customer
- `chatwoot_contact_id`: Chatwoot Contact ID
- `formbricks_contact_id`: Formbricks Contact ID

### Lead
- `chatwoot_contact_id`: Chatwoot Contact ID
- `chatwoot_conversation_id`: Linked Chatwoot Conversation
- `formbricks_contact_id`: Formbricks Contact ID
- `formbricks_response_id`: Linked Formbricks Response

### Issue
- `chatwoot_conversation_id`: Linked Chatwoot Conversation

## Scheduled Tasks

- **Hourly**: Sync contacts from Chatwoot, sync surveys from Formbricks
- **Daily**: Clean up old conversations based on retention settings

## Development

```bash
# Clone for development
git clone https://github.com/TubaApollo/erpnext-chatwoot-formbricks.git
cd erpnext-chatwoot-formbricks

# Install in development mode
bench get-app erpnext_chatwoot_formbricks --branch develop

# Run tests
bench --site your-site.local run-tests --app erpnext_chatwoot_formbricks
```

## License

MIT License - see [LICENSE](LICENSE) file.

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Support

- **Issues**: [GitHub Issues](https://github.com/TubaApollo/erpnext-chatwoot-formbricks/issues)
- **Discussions**: [GitHub Discussions](https://github.com/TubaApollo/erpnext-chatwoot-formbricks/discussions)

## Credits

- [Chatwoot](https://www.chatwoot.com/) - Open Source Customer Engagement Platform
- [Formbricks](https://formbricks.com/) - Open Source Survey Platform
- [ERPNext](https://erpnext.com/) - Open Source ERP
- [Frappe Framework](https://frappeframework.com/) - Python Web Framework
