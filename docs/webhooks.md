# Webhook Management (v3.2)

**Added in:** v3.2.0
**Module:** `api/webhook_routes.py`, `api/webhook_manager.py`

## Overview

Webhooks enable event-driven integration with external systems. ADAPT-Agents can automatically notify your systems when incidents are detected, analysis completes, or findings are discovered—without polling.

## Features

- **Event subscriptions** - Subscribe to specific event types
- **Delivery tracking** - Complete history of all webhook deliveries
- **Retry logic** - Automatic retry with exponential backoff
- **Persistent storage** - SQLite-backed configuration
- **Test endpoints** - Verify webhook configuration
- **Multiple webhooks** - Subscribe multiple URLs to same events

## Event Types

| Event | Trigger | Payload |
|-------|---------|---------|
| `analysis.started` | RCA analysis begins | Analysis ID, incident data |
| `analysis.completed` | RCA analysis finishes | Analysis ID, RCA results |
| `analysis.failed` | RCA analysis errors | Analysis ID, error details |
| `agent.completed` | Individual agent finishes | Agent name, findings |
| `finding.created` | New finding discovered | Finding details, severity |
| `phase.completed` | Analysis phase completes | Phase number, duration |

## API Endpoints

### Create Webhook
```bash
POST /api/v1/webhooks
```

**Request:**
```json
{
  "url": "https://your-server.com/webhooks/adapt",
  "events": ["analysis.completed", "finding.created"],
  "headers": {
    "X-Custom-Header": "value",
    "Authorization": "Bearer your-token"
  }
}
```

**Response:**
```json
{
  "id": "webhook_abc123",
  "url": "https://your-server.com/webhooks/adapt",
  "events": ["analysis.completed", "finding.created"],
  "created_at": "2025-01-15T10:00:00Z",
  "active": true
}
```

### List Webhooks
```bash
GET /api/v1/webhooks
```

**Response:**
```json
{
  "webhooks": [
    {
      "id": "webhook_abc123",
      "url": "https://your-server.com/webhooks/adapt",
      "events": ["analysis.completed"],
      "active": true,
      "created_at": "2025-01-15T10:00:00Z",
      "last_triggered": "2025-01-15T11:30:00Z"
    }
  ],
  "total": 1
}
```

### Get Webhook Details
```bash
GET /api/v1/webhooks/{webhook_id}
```

### Update Webhook
```bash
PATCH /api/v1/webhooks/{webhook_id}
```

**Request:**
```json
{
  "events": ["analysis.completed", "analysis.failed"],
  "active": true
}
```

### Delete Webhook
```bash
DELETE /api/v1/webhooks/{webhook_id}
```

### Get Delivery History
```bash
GET /api/v1/webhooks/{webhook_id}/deliveries?limit=50
```

**Response:**
```json
{
  "deliveries": [
    {
      "id": "delivery_xyz789",
      "webhook_id": "webhook_abc123",
      "event_type": "analysis.completed",
      "status_code": 200,
      "success": true,
      "attempts": 1,
      "delivered_at": "2025-01-15T11:30:00Z",
      "response_time_ms": 234
    },
    {
      "id": "delivery_xyz790",
      "webhook_id": "webhook_abc123",
      "event_type": "finding.created",
      "status_code": 500,
      "success": false,
      "attempts": 3,
      "error": "Connection timeout",
      "last_attempt_at": "2025-01-15T11:31:30Z"
    }
  ],
  "success_count": 1,
  "total": 2
}
```

### Test Webhook
```bash
POST /api/v1/webhooks/{webhook_id}/test
```

Sends a test event to verify configuration.

## Webhook Payload Format

All webhook deliveries use this standard format:

```json
{
  "event_id": "evt_unique123",
  "event_type": "analysis.completed",
  "timestamp": "2025-01-15T11:30:00Z",
  "data": {
    "analysis_id": "abc-123",
    "incident_id": "inc-456",
    "success": true,
    "duration_ms": 2000,
    "results": {
      "phase1": { ... },
      "phase2": { ... },
      "phase3": { ... }
    }
  }
}
```

### Event-Specific Payloads

#### analysis.completed
```json
{
  "event_type": "analysis.completed",
  "data": {
    "analysis_id": "abc-123",
    "success": true,
    "duration_ms": 2000,
    "results": {
      "root_causes": [...],
      "remediation_plans": [...]
    }
  }
}
```

#### finding.created
```json
{
  "event_type": "finding.created",
  "data": {
    "analysis_id": "abc-123",
    "agent_name": "LogAnalyzerAgent",
    "finding": {
      "description": "Error pattern detected",
      "severity": "high",
      "confidence": 0.92
    }
  }
}
```

#### analysis.failed
```json
{
  "event_type": "analysis.failed",
  "data": {
    "analysis_id": "abc-123",
    "error": "Connection timeout",
    "phase": "phase1",
    "failed_agents": ["MetricsAnalyzerAgent"]
  }
}
```

## Receiving Webhooks

### Python/Flask Example
```python
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/webhooks/adapt', methods=['POST'])
def handle_webhook():
    event = request.json
    event_type = event['event_type']

    if event_type == 'analysis.completed':
        analysis_id = event['data']['analysis_id']
        results = event['data']['results']

        # Process results
        notify_team(analysis_id, results)

        return jsonify({"status": "success"}), 200

    elif event_type == 'finding.created':
        finding = event['data']['finding']

        if finding['severity'] == 'critical':
            alert_oncall(finding)

        return jsonify({"status": "success"}), 200

    return jsonify({"status": "unknown_event"}), 200

if __name__ == '__main__':
    app.run(port=5000)
```

### Node.js/Express Example
```javascript
const express = require('express');
const app = express();

app.use(express.json());

app.post('/webhooks/adapt', (req, res) => {
  const event = req.body;
  const { event_type, data } = event;

  switch(event_type) {
    case 'analysis.completed':
      console.log(`Analysis ${data.analysis_id} completed`);
      notifyTeam(data.analysis_id, data.results);
      break;

    case 'finding.created':
      console.log(`New finding: ${data.finding.description}`);
      if (data.finding.severity === 'critical') {
        alertOnCall(data.finding);
      }
      break;

    case 'analysis.failed':
      console.error(`Analysis ${data.analysis_id} failed: ${data.error}`);
      break;
  }

  res.json({ status: 'success' });
});

app.listen(5000, () => {
  console.log('Webhook server running on port 5000');
});
```

### Verifying Webhook Signatures (Recommended)
```python
import hmac
import hashlib

def verify_webhook_signature(payload, signature, secret):
    """Verify webhook came from ADAPT-Agents"""
    expected_signature = hmac.new(
        secret.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(signature, expected_signature)

@app.route('/webhooks/adapt', methods=['POST'])
def handle_webhook():
    signature = request.headers.get('X-Webhook-Signature')
    payload = request.get_data(as_text=True)

    if not verify_webhook_signature(payload, signature, WEBHOOK_SECRET):
        return jsonify({"error": "Invalid signature"}), 401

    # Process webhook...
    return jsonify({"status": "success"}), 200
```

## Retry Logic

ADAPT-Agents automatically retries failed webhook deliveries:

1. **Immediate retry** - 0 seconds
2. **Second retry** - 5 seconds
3. **Third retry** - 30 seconds
4. **Fourth retry** - 2 minutes
5. **Final retry** - 10 minutes

After 5 failed attempts, the webhook is marked as failed and logged.

## Best Practices

### Security
1. **Use HTTPS** - Always use encrypted connections
2. **Verify signatures** - Implement signature verification
3. **API keys in headers** - Don't include secrets in URLs
4. **Whitelist IPs** - Restrict webhook receiver to known IPs
5. **Rate limiting** - Protect your webhook receiver from abuse

### Reliability
1. **Idempotency** - Handle duplicate deliveries gracefully
2. **Quick responses** - Return 200 OK within 5 seconds
3. **Async processing** - Queue webhook for background processing
4. **Error handling** - Return appropriate HTTP status codes
5. **Logging** - Log all webhook receipts for debugging

### Performance
```python
# Good: Queue for async processing
@app.route('/webhooks/adapt', methods=['POST'])
def handle_webhook():
    event = request.json

    # Queue for background processing
    queue.enqueue(process_webhook, event)

    # Return immediately
    return jsonify({"status": "queued"}), 200

# Bad: Synchronous processing blocks
@app.route('/webhooks/adapt', methods=['POST'])
def handle_webhook():
    event = request.json

    # Don't do this - will timeout!
    process_webhook(event)  # Takes 30 seconds

    return jsonify({"status": "success"}), 200
```

## Integration Examples

### Slack Notification
```python
import requests

@app.route('/webhooks/adapt', methods=['POST'])
def handle_webhook():
    event = request.json

    if event['event_type'] == 'analysis.completed':
        analysis_id = event['data']['analysis_id']
        results = event['data']['results']

        # Send to Slack
        slack_webhook = "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
        requests.post(slack_webhook, json={
            "text": f"🔍 RCA Complete: {analysis_id}",
            "attachments": [{
                "color": "good",
                "fields": [
                    {"title": "Root Cause", "value": results['root_causes'][0]},
                    {"title": "Remediation", "value": results['remediation_plans'][0]}
                ]
            }]
        })

    return jsonify({"status": "success"}), 200
```

### PagerDuty Incident
```python
@app.route('/webhooks/adapt', methods=['POST'])
def handle_webhook():
    event = request.json

    if event['event_type'] == 'finding.created':
        finding = event['data']['finding']

        if finding['severity'] == 'critical':
            # Create PagerDuty incident
            requests.post(
                "https://events.pagerduty.com/v2/enqueue",
                json={
                    "routing_key": PAGERDUTY_KEY,
                    "event_action": "trigger",
                    "payload": {
                        "summary": finding['description'],
                        "severity": "critical",
                        "source": "ADAPT-Agents"
                    }
                }
            )

    return jsonify({"status": "success"}), 200
```

### JIRA Ticket
```python
from jira import JIRA

@app.route('/webhooks/adapt', methods=['POST'])
def handle_webhook():
    event = request.json

    if event['event_type'] == 'analysis.completed':
        jira = JIRA(JIRA_URL, basic_auth=(JIRA_USER, JIRA_TOKEN))

        issue = jira.create_issue(
            project={"key": "INC"},
            summary=f"RCA: {event['data']['analysis_id']}",
            description=format_rca_results(event['data']['results']),
            issuetype={"name": "Incident"}
        )

    return jsonify({"status": "success"}), 200
```

## Monitoring & Debugging

### Check Webhook Status
```bash
# Get recent deliveries
curl http://localhost:8000/api/v1/webhooks/{webhook_id}/deliveries \
  -H "X-API-Key: demo-key-12345"

# Look for failed deliveries
curl http://localhost:8000/api/v1/webhooks/{webhook_id}/deliveries?status=failed \
  -H "X-API-Key: demo-key-12345"
```

### Test Webhook Configuration
```bash
# Send test event
curl -X POST http://localhost:8000/api/v1/webhooks/{webhook_id}/test \
  -H "X-API-Key: demo-key-12345"

# Check your server logs for the test event
```

### Common Issues

**Webhook not triggering:**
- Verify event type subscription
- Check webhook is active (`active: true`)
- Ensure analysis is creating events

**Delivery failures:**
- Verify URL is accessible from server
- Check for firewall/network restrictions
- Ensure HTTPS certificate is valid
- Verify webhook receiver returns 200 OK

**Slow deliveries:**
- Webhook receiver taking too long (>5s timeout)
- Implement async processing
- Return 200 OK immediately, process in background

## Next Steps

- Learn about [Enterprise Integrations](integrations.md) for Slack/JIRA/PagerDuty
- Explore [WebSocket Streaming](websockets.md) for real-time updates
- Check [API Reference](api_reference.md) for complete documentation
