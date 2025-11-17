# Interactive Visualizations (v3.5)

**Added in:** v3.5.0
**Modules:** `visualization/`, `api/visualization_routes.py`

## Overview

ADAPT-Agents provides production-grade interactive visualizations for RCA analysis, matching DataDog and Grafana's visualization capabilities with root cause dependency graphs, timeline charts, and metrics dashboards—all exportable in multiple formats for any frontend framework.

## Features

- 🕸️ **Root Cause Dependency Graphs** - Interactive service dependency visualization
- ⏱️ **Incident Timelines** - Chronological event visualization with markers
- 📈 **Metrics Dashboards** - Time-series charts with anomaly detection
- 🎨 **Multi-Format Export** - Cytoscape.js, D3.js, Plotly, Chart.js, GraphML, DOT
- 🔍 **Automatic Anomaly Highlighting** - Statistical detection (2σ threshold)
- 📊 **Graph Statistics** - Node counts, connectivity analysis, correlations

## Visualization Types

### 1. Root Cause Dependency Graphs
**File:** `visualization/root_cause_graph.py`

Generates interactive graphs showing relationships between incidents, services, findings, hypotheses, and remediation actions.

#### Supported Formats
- **Cytoscape.js** - Interactive web graph (force-directed)
- **D3.js** - Force-directed graph with custom styling
- **GraphML** - Standard graph exchange format (import to Gephi, etc.)
- **DOT** - Graphviz format for static rendering

#### Example
```bash
curl -X POST http://localhost:8000/api/v1/visualizations/root-cause-graph \
  -H "X-API-Key: demo-key-12345" \
  -d '{
    "rca_results": {...},
    "format": "cytoscape"
  }'
```

**Response:**
```json
{
  "format": "cytoscape",
  "data": {
    "elements": [
      {"data": {"id": "INCIDENT", "node_type": "incident", "color": "#ff0000"}},
      {"data": {"id": "service_payment-service", "node_type": "service", "color": "#4285f4"}},
      {"data": {"id": "hypothesis_1", "node_type": "hypothesis", "color": "#ff6b6b"}},
      {"data": {"source": "INCIDENT", "target": "service_payment-service", "relationship": "affects"}},
      {"data": {"source": "INCIDENT", "target": "hypothesis_1", "relationship": "root_cause"}}
    ]
  },
  "stats": {
    "total_nodes": 15,
    "total_edges": 18,
    "node_types": {
      "incident": 1,
      "service": 3,
      "finding": 8,
      "hypothesis": 2,
      "remediation": 1
    }
  }
}
```

#### Python Example
```python
from visualization import RootCauseGraphGenerator

# Generate graph
graph_gen = RootCauseGraphGenerator()
graph_data = graph_gen.generate_from_rca(rca_results)

# Access different formats
cytoscape_format = graph_data["cytoscape"]  # For Cytoscape.js
d3_format = graph_data["d3"]                # For D3.js force graph
graphml_format = graph_data["graphml"]      # For Gephi/yEd
dot_format = graph_data["dot"]              # For Graphviz
stats = graph_data["stats"]                 # Graph statistics
```

#### Web Rendering (Cytoscape.js)
```html
<!DOCTYPE html>
<html>
<head>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/cytoscape/3.23.0/cytoscape.min.js"></script>
</head>
<body>
  <div id="graph" style="width: 100%; height: 600px;"></div>

  <script>
    // Fetch graph data from API
    fetch('/api/v1/visualizations/root-cause-graph', {
      method: 'POST',
      headers: {'X-API-Key': 'demo-key-12345', 'Content-Type': 'application/json'},
      body: JSON.stringify({rca_results: {...}, format: 'cytoscape'})
    })
    .then(res => res.json())
    .then(data => {
      // Render graph
      const cy = cytoscape({
        container: document.getElementById('graph'),
        elements: data.data.elements,
        style: [
          {
            selector: 'node',
            style: {
              'background-color': 'data(color)',
              'label': 'data(label)',
              'color': '#fff',
              'text-outline-color': '#000',
              'text-outline-width': 2
            }
          },
          {
            selector: 'edge',
            style: {
              'curve-style': 'bezier',
              'target-arrow-shape': 'triangle',
              'label': 'data(relationship)'
            }
          }
        ],
        layout: {name: 'cose'}  // Force-directed layout
      });
    });
  </script>
</body>
</html>
```

#### Web Rendering (D3.js)
```javascript
// Fetch graph data
fetch('/api/v1/visualizations/root-cause-graph', {
  method: 'POST',
  headers: {'X-API-Key': 'demo-key-12345', 'Content-Type': 'application/json'},
  body: JSON.stringify({rca_results: {...}, format: 'd3'})
})
.then(res => res.json())
.then(data => {
  const {nodes, links} = data.data;

  // Create force simulation
  const simulation = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(links).id(d => d.id))
    .force('charge', d3.forceManyBody().strength(-300))
    .force('center', d3.forceCenter(width / 2, height / 2));

  // Draw nodes and links
  const svg = d3.select('#graph');

  const link = svg.append('g')
    .selectAll('line')
    .data(links)
    .enter().append('line')
    .attr('stroke', '#999');

  const node = svg.append('g')
    .selectAll('circle')
    .data(nodes)
    .enter().append('circle')
    .attr('r', 10)
    .attr('fill', d => d.color);

  simulation.on('tick', () => {
    link
      .attr('x1', d => d.source.x)
      .attr('y1', d => d.source.y)
      .attr('x2', d => d.target.x)
      .attr('y2', d => d.target.y);

    node
      .attr('cx', d => d.x)
      .attr('cy', d => d.y);
  });
});
```

### 2. Incident Timelines
**File:** `visualization/timeline_chart.py`

Creates chronological visualizations of incident events, including logs, metrics anomalies, deployments, and RCA phases.

#### Supported Formats
- **Plotly** - Interactive scatter timeline
- **Chart.js** - Canvas-based line chart
- **D3.js** - Custom SVG timeline
- **Gantt** - Task-based visualization (for agent execution)

#### Example
```bash
curl -X POST http://localhost:8000/api/v1/visualizations/timeline \
  -H "X-API-Key: demo-key-12345" \
  -d '{
    "incident_data": {
      "incident_time": "2025-01-15T10:00:00Z",
      "logs": [...],
      "metrics": [...],
      "changes": [...]
    },
    "rca_results": {...},
    "format": "plotly"
  }'
```

**Response:**
```json
{
  "format": "plotly",
  "data": {
    "data": [{
      "type": "scatter",
      "mode": "markers+text",
      "x": ["2025-01-15T09:55:00Z", "2025-01-15T09:58:00Z", "2025-01-15T10:00:00Z"],
      "y": [1, 1, 1],
      "text": ["Deployment: v1.3.0", "CPU spike detected", "Incident detected"],
      "marker": {
        "size": 15,
        "color": ["#51cf66", "#ffd43b", "#ff0000"]
      }
    }],
    "layout": {
      "title": "Incident Timeline",
      "xaxis": {"title": "Time"},
      "height": 400
    }
  },
  "stats": {
    "total_events": 15,
    "duration_seconds": 300,
    "event_types": {
      "log_error": 5,
      "metric_anomaly": 3,
      "change_deployment": 2,
      "incident_start": 1,
      "rca_complete": 1
    }
  }
}
```

#### Python Example
```python
from visualization import TimelineChartGenerator

# Generate timeline
timeline_gen = TimelineChartGenerator()
timeline_data = timeline_gen.generate_from_incident(
    incident_data=incident_data,
    rca_results=rca_results
)

# Access formats
plotly_chart = timeline_data["plotly"]
chartjs_chart = timeline_data["chartjs"]
d3_timeline = timeline_data["d3_timeline"]
gantt_chart = timeline_data["gantt"]
```

#### Web Rendering (Plotly)
```html
<script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
<div id="timeline"></div>

<script>
fetch('/api/v1/visualizations/timeline', {
  method: 'POST',
  headers: {'X-API-Key': 'demo-key-12345', 'Content-Type': 'application/json'},
  body: JSON.stringify({
    incident_data: {...},
    rca_results: {...},
    format: 'plotly'
  })
})
.then(res => res.json())
.then(data => {
  Plotly.newPlot('timeline', data.data.data, data.data.layout);
});
</script>
```

#### Web Rendering (Chart.js)
```html
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<canvas id="timeline"></canvas>

<script>
fetch('/api/v1/visualizations/timeline', {
  method: 'POST',
  headers: {'X-API-Key': 'demo-key-12345', 'Content-Type': 'application/json'},
  body: JSON.stringify({
    incident_data: {...},
    format: 'chartjs'
  })
})
.then(res => res.json())
.then(data => {
  const ctx = document.getElementById('timeline').getContext('2d');
  new Chart(ctx, data.data);
});
</script>
```

### 3. Metrics Dashboards
**File:** `visualization/metrics_dashboard.py`

Generates interactive metric visualizations with automatic anomaly detection and highlighting.

#### Features
- Time-series metric charts
- Anomaly detection (2σ threshold)
- Anomaly highlighting with markers
- Correlation heatmap
- Summary statistics panel (min, max, avg, current, % change)

#### Example
```bash
curl -X POST http://localhost:8000/api/v1/visualizations/metrics-dashboard \
  -H "X-API-Key: demo-key-12345" \
  -d '{
    "metrics": [
      {
        "name": "cpu_usage",
        "service": "payment-service",
        "values": [45, 50, 55, 85, 90, 92, 60],
        "timestamps": ["10:00", "10:01", "10:02", "10:03", "10:04", "10:05", "10:06"],
        "unit": "%"
      }
    ],
    "incident_time": "2025-01-15T10:03:00Z",
    "format": "plotly"
  }'
```

**Response:**
```json
{
  "format": "plotly",
  "data": {
    "data": [
      {
        "type": "scatter",
        "mode": "lines+markers",
        "name": "cpu_usage",
        "x": ["10:00", "10:01", "10:02", "10:03", "10:04", "10:05", "10:06"],
        "y": [45, 50, 55, 85, 90, 92, 60]
      },
      {
        "type": "scatter",
        "mode": "markers",
        "name": "cpu_usage Anomalies",
        "x": ["10:03", "10:04", "10:05"],
        "y": [85, 90, 92],
        "marker": {"size": 12, "color": "#ff0000", "symbol": "x"}
      }
    ],
    "layout": {
      "title": "Metrics Dashboard",
      "height": 300
    }
  },
  "anomalies": [
    {
      "metric_name": "cpu_usage",
      "service": "payment-service",
      "anomaly_count": 3,
      "anomaly_indices": [3, 4, 5],
      "severity": "high"
    }
  ]
}
```

#### Python Example
```python
from visualization import MetricsDashboardGenerator

# Generate dashboard
dashboard_gen = MetricsDashboardGenerator()
dashboard_data = dashboard_gen.generate_from_metrics(
    metrics=metrics_list,
    incident_time="2025-01-15T10:03:00Z"
)

# Access components
charts = dashboard_data["charts"]  # Individual metric charts
heatmap = dashboard_data["heatmap"]  # Correlation heatmap
summary = dashboard_data["summary"]  # Summary statistics
anomalies = dashboard_data["anomalies"]  # Detected anomalies
```

### 4. Complete Dashboard
**Endpoint:** `POST /api/v1/visualizations/complete-dashboard`

Generates all visualizations in one call - convenience endpoint combining root cause graph, timeline, and metrics dashboard.

```bash
curl -X POST http://localhost:8000/api/v1/visualizations/complete-dashboard \
  -H "X-API-Key: demo-key-12345" \
  -d '{
    "incident_data": {...},
    "rca_results": {...}
  }'
```

**Response:**
```json
{
  "root_cause_graph": {
    "cytoscape": {...},
    "d3": {...},
    "stats": {...}
  },
  "timeline": {
    "plotly": {...},
    "events": [...],
    "stats": {...}
  },
  "metrics_dashboard": {
    "plotly_dashboard": {...},
    "anomalies": [...],
    "stats": {...}
  },
  "summary": {
    "total_visualizations": 3,
    "formats_available": ["cytoscape", "d3", "plotly", "chartjs"]
  }
}
```

## Anomaly Detection

### Algorithm
- **Statistical Method:** Mean ± 2σ (standard deviation)
- **Threshold:** Values beyond 2 standard deviations flagged as anomalies
- **Minimum Data Points:** Requires ≥3 data points for detection

### Example
```python
# Metric values: [45, 50, 55, 85, 90, 92, 60]
# Mean: 68.14
# Std Dev: 19.87
# Threshold: 68.14 ± (2 × 19.87) = [28.4, 107.9]

# Anomalies: None (all values within range)
# But with stricter threshold (1.5σ):
# Anomalies at indices: [3, 4, 5] (values: 85, 90, 92)
```

## Use Cases

### 1. War Room Dashboard
Display real-time RCA progress:
```javascript
// WebSocket + Complete Dashboard
const ws = new WebSocket('ws://localhost:8000/ws/analysis/abc-123');

ws.onmessage = async (event) => {
  const update = JSON.parse(event.data);

  if (update.type === 'analysis_complete') {
    // Fetch and render complete dashboard
    const response = await fetch('/api/v1/visualizations/complete-dashboard', {
      method: 'POST',
      headers: {'X-API-Key': 'demo-key-12345', 'Content-Type': 'application/json'},
      body: JSON.stringify({
        incident_data: incidentData,
        rca_results: update.results
      })
    });

    const dashboard = await response.json();

    // Render root cause graph
    renderCytoscapeGraph(dashboard.root_cause_graph.cytoscape);

    // Render timeline
    Plotly.newPlot('timeline', dashboard.timeline.plotly.data, dashboard.timeline.plotly.layout);

    // Render metrics
    Plotly.newPlot('metrics', dashboard.metrics_dashboard.plotly_dashboard.data);
  }
};
```

### 2. Incident Report Generation
Export visualizations for documentation:
```python
# Generate complete dashboard
response = requests.post('/api/v1/visualizations/complete-dashboard', ...)

# Save graphs for report
root_cause_graphml = response['root_cause_graph']['graphml']
with open('incident_graph.graphml', 'w') as f:
    f.write(root_cause_graphml)

# Export to Gephi/yEd for further analysis
```

### 3. Pattern Analysis
Identify recurring issues visually:
```bash
# Generate graphs for multiple similar incidents
for incident in similar_incidents:
  curl -X POST /api/v1/visualizations/root-cause-graph \
    -d '{"rca_results": ${incident.rca_results}}'

# Compare graphs to identify common patterns
# - Same services involved?
# - Similar root causes?
# - Common remediation strategies?
```

## Performance

### Generation Speed
- **Root Cause Graph:** <50ms for typical RCA (10-20 nodes)
- **Timeline:** <30ms for 100 events
- **Metrics Dashboard:** <20ms per metric

### Rendering Performance
- **Cytoscape.js:** Handles 1000+ nodes smoothly
- **D3.js:** Optimized for 100-500 nodes
- **Plotly:** Handles 10K+ data points

## Best Practices

### Graph Visualization
1. **Limit node count** - Filter to most relevant findings
2. **Use colors consistently** - Same node types = same colors
3. **Interactive exploration** - Enable zoom, pan, click-to-details
4. **Responsive design** - Adjust layout for mobile/desktop

### Timeline Visualization
1. **Group similar events** - Don't show every single log entry
2. **Use markers** - Distinguish event types with icons/colors
3. **Enable zooming** - Allow users to focus on specific time ranges
4. **Show duration** - Indicate how long incidents/phases lasted

### Metrics Dashboards
1. **Highlight anomalies** - Make them visually prominent
2. **Show thresholds** - Display normal vs. abnormal ranges
3. **Enable filtering** - Let users focus on specific metrics
4. **Correlation analysis** - Show related metrics together

## Export Formats

### Cytoscape.js
- **Best for:** Interactive web applications
- **Browser support:** All modern browsers
- **Features:** Zoom, pan, layouts, styling

### D3.js
- **Best for:** Custom visualizations
- **Learning curve:** Moderate to high
- **Features:** Full control over rendering

### Plotly
- **Best for:** Scientific/analytical charts
- **Features:** Interactive, publication-quality
- **Export:** PNG, SVG, PDF

### Chart.js
- **Best for:** Simple, beautiful charts
- **Performance:** Fast canvas rendering
- **Features:** Responsive, animated

### GraphML
- **Best for:** Analysis in external tools (Gephi, yEd)
- **Standard format:** Industry-standard graph format
- **Features:** Preserves all node/edge properties

### DOT (Graphviz)
- **Best for:** Static graph rendering
- **Tools:** Graphviz, dot command
- **Output:** SVG, PNG, PDF

## Next Steps

- Learn about [WebSocket Streaming](websockets.md)
- Explore [Enterprise Integrations](integrations.md)
- Check [API Reference](api_reference.md)
