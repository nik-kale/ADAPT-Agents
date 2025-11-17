# Enterprise Integrations (v3.4)

**Added in:** v3.4.0
**Modules:** `integrations/`, `api/integrations_routes.py`

## Overview

ADAPT-Agents provides native integrations with major enterprise platforms (Slack, JIRA, PagerDuty), enabling seamless incident notifications, ticket creation, and alerting workflows that match industry-leading observability platforms.

## Supported Platforms

| Platform | Capabilities | API Type |
|----------|--------------|----------|
| **Slack** | Alerts, RCA summaries, findings | Webhooks + Bot API |
| **JIRA** | Ticket creation, comments, sub-tasks | REST API v3 |
| **PagerDuty** | Incidents, notes, acknowledgments | Events + REST API |

## Quick Start

### 1. Configure Slack
```bash
curl -X POST http://localhost:8000/api/v1/integrations/slack \
  -H "X-API-Key: demo-key-12345" \
  -d '{
    "webhook_url": "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
  }'
```

### 2. Send Incident Alert
```bash
curl -X POST http://localhost:8000/api/v1/integrations/notify/incident \
  -H "X-API-Key: demo-key-12345" \
  -d '{
    "incident_id": "inc-123",
    "incident_data": {
      "incident_time": "2025-01-15T10:00:00Z",
      "severity": "critical",
      "affected_services": ["payment-service"]
    },
    "slack_channel": "#incidents",
    "create_jira": true,
    "trigger_pagerduty": true
  }'
```

### 3. Send RCA Results
```bash
curl -X POST http://localhost:8000/api/v1/integrations/notify/rca-complete \
  -H "X-API-Key: demo-key-12345" \
  -d '{
    "incident_id": "inc-123",
    "rca_results": {...},
    "slack_channel": "#incidents",
    "jira_issue_key": "INC-123",
    "pagerduty_incident_id": "PD123"
  }'
```

---

## Slack Integration

### Features
- 📱 Rich message formatting with Slack Blocks
- 🚨 Severity-based emoji indicators
- 🔔 Real-time incident alerts
- ✅ RCA completion summaries
- 🔍 Finding notifications
- 🧵 Thread support

### Configuration

#### Webhook URL (Simple)
```bash
POST /api/v1/integrations/slack
{
  "webhook_url": "https://hooks.slack.com/services/T00/B00/XXX"
}
```

#### Bot Token (Full API)
```bash
POST /api/v1/integrations/slack
{
  "bot_token": "xoxb-your-bot-token"
}
```

### Message Examples

#### Incident Alert
```json
{
  "blocks": [
    {
      "type": "header",
      "text": {"type": "plain_text", "text": "🔴 New Incident Alert"}
    },
    {
      "type": "section",
      "fields": [
        {"type": "mrkdwn", "text": "*Incident ID:*\ninc-123"},
        {"type": "mrkdwn", "text": "*Severity:*\nCRITICAL"},
        {"type": "mrkdwn", "text": "*Services:*\npayment-service"},
        {"type": "mrkdwn", "text": "*Time:*\n2025-01-15T10:00:00Z"}
      ]
    },
    {
      "type": "context",
      "elements": [
        {"type": "mrkdwn", "text": "🤖 ADAPT-Agents is analyzing..."}
      ]
    }
  ]
}
```

#### RCA Complete
```json
{
  "blocks": [
    {
      "type": "header",
      "text": {"type": "plain_text", "text": "✅ RCA Analysis Complete"}
    },
    {
      "type": "section",
      "text": {
        "type": "mrkdwn",
        "text": "*🔍 Root Cause:*\nMemory leak in user profile feature"
      }
    },
    {
      "type": "section",
      "text": {
        "type": "mrkdwn",
        "text": "*🔧 Recommended Action:*\nRollback deployment to v1.2.3"
      }
    },
    {
      "type": "context",
      "elements": [
        {"type": "mrkdwn", "text": "⏱️ Analysis completed in 2.5s"}
      ]
    }
  ]
}
```

### Python Example
```python
from integrations import SlackIntegration

# Initialize
slack = SlackIntegration(
    webhook_url="https://hooks.slack.com/services/..."
)

# Send incident alert
await slack.send_incident_alert(
    incident_id="inc-123",
    incident_data={
        "incident_time": "2025-01-15T10:00:00Z",
        "severity": "critical",
        "affected_services": ["payment-service"]
    },
    channel="#incidents"
)

# Send RCA summary
await slack.send_rca_summary(
    incident_id="inc-123",
    rca_results=rca_analysis_results,
    channel="#incidents"
)

# Send custom message
await slack.send_custom_message(
    text="Custom alert message",
    channel="#incidents"
)
```

---

## JIRA Integration

### Features
- 🎫 Automatic ticket creation
- 💬 RCA results as comments
- ✅ Remediation tasks as sub-tickets
- 🔄 Status transitions
- 🎯 Priority mapping
- 📎 Custom fields support

### Configuration
```bash
POST /api/v1/integrations/jira
{
  "jira_url": "https://your-company.atlassian.net",
  "username": "your-email@company.com",
  "api_token": "your-api-token",
  "project_key": "INCIDENT"
}
```

### Ticket Creation
```bash
# Automatically creates ticket with:
# - Summary: [inc-123] Incident in payment-service
# - Description: Full incident details
# - Priority: Mapped from severity (critical → Highest)
# - Type: Bug/Incident
```

#### Ticket Format
```
Summary: [inc-123] Incident in payment-service

Description:
*Incident ID:* inc-123
*Time:* 2025-01-15T10:00:00Z
*Severity:* Critical
*Affected Services:* payment-service

*Recent Error Logs:*
- OutOfMemoryError: Java heap space
- Connection pool exhausted
- Payment processing timeout

*Key Metrics:*
- memory_usage_percent
- error_rate_per_minute
```

### RCA Comment
```
*Root Cause Analysis Complete*

*Root Cause:*
1. Memory leak in user profile caching
   - Confidence: high

*Recommended Actions:*
1. Rollback deployment to v1.2.3
   - Priority: immediate
   - Estimated Time: 15 minutes
2. Add heap dump analysis to diagnostics
   - Priority: short-term
   - Estimated Time: 2 hours

_Analysis completed in 2.5s_
```

### Remediation Sub-Tasks
```bash
# Automatically creates sub-tasks:
- [SUB-1] Remediation 1: Rollback deployment (Priority: Highest)
- [SUB-2] Remediation 2: Add heap analysis (Priority: High)
- [SUB-3] Remediation 3: Update monitoring (Priority: Medium)
```

### Python Example
```python
from integrations import JiraIntegration

# Initialize
jira = JiraIntegration(
    jira_url="https://company.atlassian.net",
    username="user@company.com",
    api_token="your-api-token",
    project_key="INCIDENT"
)

# Create incident ticket
result = await jira.create_incident_ticket(
    incident_id="inc-123",
    incident_data=incident_data,
    issue_type="Bug"
)
# Returns: {"issue_key": "INC-123", "url": "https://..."}

# Add RCA comment
await jira.add_rca_comment(
    issue_key="INC-123",
    rca_results=rca_results
)

# Create remediation sub-tasks
await jira.create_remediation_tasks(
    parent_issue_key="INC-123",
    remediation_findings=remediation_findings
)

# Update status
await jira.update_issue_status(
    issue_key="INC-123",
    transition_name="Resolved"
)
```

---

## PagerDuty Integration

### Features
- 🚨 Trigger incidents via Events API
- 📝 Add RCA notes
- ✅ Acknowledge incidents
- ✔️ Resolve incidents
- 🎯 Urgency mapping
- 📊 Custom details

### Configuration
```bash
POST /api/v1/integrations/pagerduty
{
  "api_key": "your-pagerduty-api-key",
  "integration_key": "your-events-integration-key",
  "from_email": "your-email@company.com"
}
```

### Trigger Incident (Events API)
```python
from integrations import PagerDutyIntegration

pd = PagerDutyIntegration(
    api_key="pd-api-key",
    integration_key="events-integration-key"
)

# Trigger incident
await pd.trigger_incident(
    incident_id="inc-123",
    incident_data={
        "incident_time": "2025-01-15T10:00:00Z",
        "severity": "critical",
        "affected_services": ["payment-service"],
        "logs": [...]
    }
)
```

### Create Incident (REST API)
```python
# More control via REST API
await pd.create_incident(
    incident_id="inc-123",
    incident_data=incident_data,
    service_id="PSERVICE123",
    urgency="high"
)
```

### Add RCA Note
```python
await pd.add_rca_note(
    incident_id="PD_INCIDENT_ID",
    rca_results={
        "phase2": {"hypothesis_generator": {...}},
        "phase3": {"remediation_planner": {...}}
    }
)
```

### Resolve/Acknowledge
```python
# Acknowledge
await pd.acknowledge_incident("inc-123")

# Resolve
await pd.resolve_incident(
    incident_id="inc-123",
    resolution="Rolled back deployment, monitoring for 24h"
)
```

---

## Integration Manager

Centralized management of all integrations:

```python
from integrations import IntegrationManager

manager = IntegrationManager()

# Register integrations (done once)
manager.register_slack(integration_id, api_key, webhook_url)
manager.register_jira(integration_id, api_key, jira_url, username, token, project_key)
manager.register_pagerduty(integration_id, api_key, pd_api_key, integration_key)

# Notify all configured integrations at once
await manager.notify_incident(
    incident_id="inc-123",
    incident_data=incident_data,
    api_key=api_key,
    slack_channel="#incidents",
    create_jira=True,
    trigger_pagerduty=True
)

# Notify RCA complete to all
await manager.notify_rca_complete(
    incident_id="inc-123",
    rca_results=rca_results,
    api_key=api_key,
    slack_channel="#incidents",
    jira_issue_key="INC-123",
    pagerduty_incident_id="PD123"
)

# List all integrations
integrations = manager.list_integrations(api_key)

# Test all integrations
test_results = await manager.test_all_integrations(api_key)
```

## API Endpoints

### List Integrations
```bash
GET /api/v1/integrations
```

**Response:**
```json
{
  "integrations": [
    {
      "id": "int-slack-1",
      "integration_type": "slack",
      "enabled": true,
      "created_at": "2025-01-15T10:00:00Z",
      "last_used": "2025-01-15T11:30:00Z"
    },
    {
      "id": "int-jira-1",
      "integration_type": "jira",
      "enabled": true
    }
  ],
  "total": 2
}
```

### Delete Integration
```bash
DELETE /api/v1/integrations/{integration_id}
```

### Test Integrations
```bash
POST /api/v1/integrations/test
```

**Response:**
```json
{
  "test_results": {
    "int-slack-1": {
      "type": "slack",
      "test": {"success": true, "message": "Connection successful"}
    },
    "int-jira-1": {
      "type": "jira",
      "test": {"success": true, "user": "John Doe"}
    },
    "int-pd-1": {
      "type": "pagerduty",
      "test": {"success": true, "abilities": ["manage_incidents"]}
    }
  },
  "total_tested": 3
}
```

## Use Cases

### 1. Incident War Room
```bash
# Create Slack thread, JIRA ticket, and PagerDuty incident simultaneously
curl -X POST /api/v1/integrations/notify/incident \
  -d '{
    "incident_id": "inc-123",
    "incident_data": {...},
    "slack_channel": "#war-room",
    "create_jira": true,
    "trigger_pagerduty": true
  }'

# Result:
# - Slack: Alert posted to #war-room
# - JIRA: Ticket INC-123 created
# - PagerDuty: On-call engineer paged
```

### 2. Automated Runbook
```bash
# When RCA completes, update all platforms
curl -X POST /api/v1/integrations/notify/rca-complete \
  -d '{
    "incident_id": "inc-123",
    "rca_results": {...},
    "slack_channel": "#war-room",
    "jira_issue_key": "INC-123",
    "pagerduty_incident_id": "PD123"
  }'

# Result:
# - Slack: RCA summary with root cause + remediation
# - JIRA: Comment added with detailed findings
# - PagerDuty: Note added, incident can be resolved
```

### 3. Critical Alert Escalation
```python
# Filter by severity before sending
if incident_data['severity'] == 'critical':
    await manager.notify_incident(
        incident_id=incident_id,
        incident_data=incident_data,
        api_key=api_key,
        slack_channel="#critical-alerts",
        create_jira=True,
        trigger_pagerduty=True
    )
else:
    # Only Slack for non-critical
    await manager.notify_incident(
        incident_id=incident_id,
        incident_data=incident_data,
        api_key=api_key,
        slack_channel="#incidents",
        create_jira=False,
        trigger_pagerduty=False
    )
```

## Best Practices

### Security
1. **Store credentials securely** - Use environment variables or secrets manager
2. **Rotate API tokens regularly** - Set expiration reminders
3. **Use dedicated service accounts** - Don't use personal accounts
4. **Audit integration usage** - Review last_used timestamps
5. **Enable MFA** - On all integrated platforms

### Reliability
1. **Test integrations before production** - Use test endpoints
2. **Monitor delivery success** - Check integration logs
3. **Handle rate limits** - Implement exponential backoff
4. **Set timeouts** - Don't wait forever for external APIs
5. **Fallback mechanisms** - Continue analysis even if integration fails

### Performance
1. **Async notifications** - Don't block analysis
2. **Batch updates** - Combine multiple updates when possible
3. **Cache API responses** - Reduce external API calls
4. **Limit payload size** - Truncate large log dumps
5. **Background processing** - Use task queues for heavy operations

## Troubleshooting

### Slack: Message Not Sent
- Verify webhook URL is correct
- Check Slack workspace hasn't disabled incoming webhooks
- Ensure bot has permission to post to channel
- Test with simple message first

### JIRA: Ticket Creation Failed
- Verify JIRA URL, username, and API token
- Check project key exists and is accessible
- Ensure user has create permission in project
- Verify issue type (Bug/Incident) exists in project

### PagerDuty: Incident Not Triggered
- Verify integration_key is correct
- Check service is not paused/disabled
- Ensure API key has permission to create incidents
- Test with Events API directly first

## Next Steps

- Learn about [Interactive Visualizations](visualizations.md)
- Explore [WebSocket Streaming](websockets.md)
- Check [API Reference](api_reference.md)
