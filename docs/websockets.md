# Real-Time Streaming with WebSockets (v3.2)

**Added in:** v3.2.0
**Module:** `api/websocket_routes.py`, `api/websocket_manager.py`, `chains/streaming_orchestrator.py`

## Overview

ADAPT-Agents provides real-time WebSocket streaming for live updates during RCA analysis. This enables users to monitor agent execution in real-time, receive intermediate findings as they're discovered, and track analysis progress without polling.

## Features

- **Live agent execution updates** - Start/complete events for each agent
- **Real-time findings** - Individual findings streamed as discovered
- **Phase transition tracking** - Know when analysis moves between phases
- **Multiple connection types** - Analysis-specific, broadcast, and agent-specific streams
- **Automatic keepalive** - Ping/pong heartbeat support
- **Error handling** - Graceful disconnection and reconnection

## WebSocket Endpoints

### 1. Analysis-Specific Stream
```
ws://localhost:8000/ws/analysis/{analysis_id}
```

Receive updates for a specific RCA analysis.

**Use case:** Monitor a particular incident analysis in real-time.

### 2. Broadcast Stream
```
ws://localhost:8000/ws/broadcast
```

Receive all system-wide events.

**Use case:** Dashboard showing all ongoing analyses.

### 3. Agent-Specific Stream
```
ws://localhost:8000/ws/agent/{agent_name}
```

Receive updates from a specific agent across all analyses.

**Use case:** Monitor performance of a particular agent type.

## Message Types

### Agent Status Update
```json
{
  "type": "agent_status",
  "timestamp": "2025-01-15T10:30:00Z",
  "analysis_id": "abc-123",
  "agent_name": "LogAnalyzerAgent",
  "status": "running",
  "progress": 50.0,
  "message": "Analyzing error logs..."
}
```

### Phase Status Update
```json
{
  "type": "phase_status",
  "timestamp": "2025-01-15T10:31:00Z",
  "analysis_id": "abc-123",
  "phase": "phase1",
  "status": "completed",
  "duration_ms": 1234
}
```

### Finding Update
```json
{
  "type": "finding",
  "timestamp": "2025-01-15T10:30:30Z",
  "analysis_id": "abc-123",
  "agent_name": "MetricsAnalyzerAgent",
  "finding": {
    "description": "CPU spike detected at 14:29:00",
    "severity": "high",
    "confidence": 0.92
  }
}
```

### Analysis Complete
```json
{
  "type": "analysis_complete",
  "timestamp": "2025-01-15T10:32:00Z",
  "analysis_id": "abc-123",
  "success": true,
  "total_duration_ms": 2000
}
```

### Error
```json
{
  "type": "error",
  "timestamp": "2025-01-15T10:30:45Z",
  "analysis_id": "abc-123",
  "error": "Agent execution failed: connection timeout"
}
```

## Client Examples

### JavaScript/Browser
```javascript
// Connect to analysis stream
const ws = new WebSocket('ws://localhost:8000/ws/analysis/abc-123');

ws.onopen = () => {
  console.log('WebSocket connected');
};

ws.onmessage = (event) => {
  const update = JSON.parse(event.data);

  switch(update.type) {
    case 'agent_status':
      console.log(`[${update.agent_name}] ${update.status}: ${update.message}`);
      updateProgressBar(update.progress);
      break;

    case 'finding':
      console.log(`New finding: ${update.finding.description}`);
      addFindingToUI(update.finding);
      break;

    case 'analysis_complete':
      console.log('Analysis complete!');
      showResults();
      ws.close();
      break;

    case 'error':
      console.error('Analysis error:', update.error);
      showError(update.error);
      break;
  }
};

ws.onerror = (error) => {
  console.error('WebSocket error:', error);
};

ws.onclose = () => {
  console.log('WebSocket closed');
};

// Send ping to keep connection alive
setInterval(() => {
  if (ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({type: 'ping'}));
  }
}, 30000); // Every 30 seconds
```

### Python Client
```python
import asyncio
import websockets
import json

async def monitor_analysis(analysis_id):
    uri = f"ws://localhost:8000/ws/analysis/{analysis_id}"

    async with websockets.connect(uri) as websocket:
        print(f"Connected to analysis {analysis_id}")

        async for message in websocket:
            update = json.loads(message)

            if update['type'] == 'agent_status':
                print(f"[{update['agent_name']}] {update['status']}: {update['message']}")

            elif update['type'] == 'finding':
                print(f"Finding: {update['finding']['description']}")

            elif update['type'] == 'analysis_complete':
                print("Analysis complete!")
                break

            elif update['type'] == 'error':
                print(f"Error: {update['error']}")
                break

asyncio.run(monitor_analysis("abc-123"))
```

### React Component
```jsx
import React, { useEffect, useState } from 'react';

function AnalysisMonitor({ analysisId }) {
  const [status, setStatus] = useState('Connecting...');
  const [findings, setFindings] = useState([]);
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    const ws = new WebSocket(`ws://localhost:8000/ws/analysis/${analysisId}`);

    ws.onopen = () => setStatus('Connected');

    ws.onmessage = (event) => {
      const update = JSON.parse(event.data);

      switch(update.type) {
        case 'agent_status':
          setStatus(`${update.agent_name}: ${update.message}`);
          setProgress(update.progress);
          break;

        case 'finding':
          setFindings(prev => [...prev, update.finding]);
          break;

        case 'analysis_complete':
          setStatus('Analysis Complete');
          setProgress(100);
          ws.close();
          break;
      }
    };

    return () => ws.close();
  }, [analysisId]);

  return (
    <div>
      <h2>Analysis Monitor</h2>
      <p>Status: {status}</p>
      <progress value={progress} max="100">{progress}%</progress>

      <h3>Findings ({findings.length})</h3>
      <ul>
        {findings.map((finding, idx) => (
          <li key={idx}>
            <strong>{finding.severity}</strong>: {finding.description}
          </li>
        ))}
      </ul>
    </div>
  );
}
```

## Server-Side Implementation

### Streaming Orchestrator
```python
from chains.streaming_orchestrator import StreamingOrchestrator
from api.websocket_manager import manager as ws_manager

# Create streaming orchestrator
orchestrator = StreamingOrchestrator(
    websocket_manager=ws_manager,
    analysis_id=analysis_id,
    error_strategy="continue",
    use_llm=True
)

# Execute RCA - updates are automatically streamed via WebSocket
results = await orchestrator.execute_rca_chain(incident_data)

# All agent events are automatically sent to connected WebSocket clients
```

### Manual WebSocket Sending
```python
from api.websocket_manager import manager

# Send agent status
await manager.send_agent_status(
    analysis_id="abc-123",
    agent_name="LogAnalyzerAgent",
    status="running",
    progress=50.0,
    message="Processing error logs..."
)

# Send finding
await manager.send_finding(
    analysis_id="abc-123",
    agent_name="MetricsAnalyzerAgent",
    finding={
        "description": "CPU spike at 95%",
        "severity": "high",
        "confidence": 0.92
    }
)

# Send phase status
await manager.send_phase_status(
    analysis_id="abc-123",
    phase="phase1",
    status="completed",
    duration_ms=1234
)

# Send analysis complete
await manager.send_analysis_complete(
    analysis_id="abc-123",
    success=True,
    results=results
)

# Send error
await manager.send_error(
    analysis_id="abc-123",
    error="Connection timeout"
)
```

## Architecture

```
┌─────────────────────┐
│   WebSocket Client  │
│   (Browser/Python)  │
└──────────┬──────────┘
           │ WebSocket Connection
           ↓
┌─────────────────────┐
│  WebSocket Router   │
│  /ws/analysis/{id}  │
└──────────┬──────────┘
           │
           ↓
┌─────────────────────┐
│ Connection Manager  │
│  (Active Connections)│
└──────────┬──────────┘
           │
           ↓
┌─────────────────────┐
│ Streaming Orchestr. │
│ (Agent Execution)   │
└─────────────────────┘
```

## Best Practices

### Client-Side
1. **Implement reconnection logic** - Handle disconnections gracefully
2. **Send periodic pings** - Keep connection alive (every 30s)
3. **Handle all message types** - Don't assume only specific messages
4. **Close connections** - Always clean up when done
5. **Error handling** - Catch WebSocket errors and connection failures

### Server-Side
1. **Limit connections** - Prevent resource exhaustion
2. **Timeout inactive connections** - Clean up stale connections
3. **Rate limiting** - Prevent abuse
4. **Authentication** - Verify client before accepting connection
5. **Logging** - Track connections and errors

## Performance Considerations

- **Concurrent Connections:** Default limit is 1000 per server
- **Message Size:** Keep messages under 64KB for optimal performance
- **Frequency:** Limit updates to avoid overwhelming clients
- **Keepalive:** Default ping interval is 30 seconds
- **Backpressure:** Slow clients are automatically disconnected

## Troubleshooting

### Connection Refused
```bash
# Check if WebSocket server is running
curl -i -N \
  -H "Connection: Upgrade" \
  -H "Upgrade: websocket" \
  -H "Sec-WebSocket-Version: 13" \
  -H "Sec-WebSocket-Key: test" \
  http://localhost:8000/ws/analysis/test
```

### No Messages Received
- Verify analysis ID is correct
- Check if analysis is actually running
- Ensure WebSocket connection is not being proxied/filtered
- Check server logs for errors

### Connection Drops
- Implement ping/pong keepalive
- Check network stability
- Verify server timeout settings
- Use reconnection with exponential backoff

## Security

### Authentication
Currently, WebSocket endpoints are open. To add authentication:

```python
from fastapi import WebSocket, HTTPException, Depends

async def verify_websocket_token(websocket: WebSocket, token: str):
    if not is_valid_token(token):
        await websocket.close(code=1008)
        return False
    return True

@router.websocket("/ws/analysis/{analysis_id}")
async def websocket_analysis_endpoint(
    websocket: WebSocket,
    analysis_id: str,
    token: str = Query(...)
):
    if not await verify_websocket_token(websocket, token):
        return

    await manager.connect(websocket, analysis_id)
    # ... rest of implementation
```

### Rate Limiting
```python
from collections import defaultdict
import time

connection_counts = defaultdict(int)

async def check_rate_limit(client_ip: str):
    if connection_counts[client_ip] > 10:  # Max 10 connections per IP
        raise HTTPException(status_code=429, detail="Too many connections")
    connection_counts[client_ip] += 1
```

## Next Steps

- Learn about [Webhook Management](webhooks.md) for event-driven callbacks
- Explore [RAG & Historical Learning](rag.md) for AI-powered analysis
- Check [API Reference](api_reference.md) for complete endpoint documentation
