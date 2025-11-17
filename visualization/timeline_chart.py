"""
Timeline Chart Generator
Creates interactive timeline visualizations of incidents and events
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import json


class TimelineChartGenerator:
    """
    Generates interactive timeline charts

    Features:
    - Incident event timeline
    - Log events visualization
    - Metric anomaly markers
    - Change deployment markers
    - Interactive zooming and filtering
    - Exportable to Plotly, Chart.js, D3.js formats
    """

    def __init__(self):
        """Initialize timeline generator"""
        self.events = []

    def generate_from_incident(
        self,
        incident_data: Dict[str, Any],
        rca_results: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate timeline from incident data

        Args:
            incident_data: Incident details with logs, metrics, changes
            rca_results: Optional RCA results to add findings

        Returns:
            Timeline data in multiple formats
        """
        self.events = []

        # Add incident start marker
        incident_time = incident_data.get("incident_time")
        if incident_time:
            self.events.append({
                "time": incident_time,
                "type": "incident_start",
                "label": "Incident Detected",
                "color": "#ff0000",
                "icon": "alert-circle",
                "severity": "critical"
            })

        # Add log events
        if "logs" in incident_data:
            self._add_log_events(incident_data["logs"])

        # Add metric anomalies
        if "metrics" in incident_data:
            self._add_metric_events(incident_data["metrics"])

        # Add changes/deployments
        if "changes" in incident_data:
            self._add_change_events(incident_data["changes"])

        # Add RCA findings if available
        if rca_results:
            self._add_rca_events(rca_results, incident_time)

        # Sort events by time
        self.events.sort(key=lambda e: e["time"])

        return {
            "events": self.events,
            "plotly": self._to_plotly(),
            "chartjs": self._to_chartjs(),
            "d3_timeline": self._to_d3_timeline(),
            "gantt": self._to_gantt(),
            "stats": self._get_stats()
        }

    def _add_log_events(self, logs: List[Dict[str, Any]]):
        """Add log entries to timeline"""
        # Group by severity and take representative samples
        error_logs = [log for log in logs if log.get("level") == "ERROR"][:10]
        warn_logs = [log for log in logs if log.get("level") == "WARN"][:5]

        for log in error_logs:
            self.events.append({
                "time": log.get("timestamp", ""),
                "type": "log_error",
                "label": log.get("message", "")[:100],
                "color": "#ff6b6b",
                "icon": "x-circle",
                "severity": "high",
                "service": log.get("service", "unknown"),
                "full_message": log.get("message", "")
            })

        for log in warn_logs:
            self.events.append({
                "time": log.get("timestamp", ""),
                "type": "log_warn",
                "label": log.get("message", "")[:100],
                "color": "#ffa500",
                "icon": "alert-triangle",
                "severity": "medium",
                "service": log.get("service", "unknown")
            })

    def _add_metric_events(self, metrics: List[Dict[str, Any]]):
        """Add metric anomalies to timeline"""
        for metric in metrics[:5]:  # Limit to top 5 metrics
            # Detect if metric has anomalous values (simple heuristic)
            values = metric.get("values", [])
            if not values:
                continue

            # Check if latest value is significantly higher than average
            avg = sum(values) / len(values)
            latest = values[-1]

            if latest > avg * 1.5:  # 50% above average
                # Estimate timestamp (use metric metadata or incident time)
                timestamp = metric.get("timestamp", metric.get("latest_timestamp", ""))

                self.events.append({
                    "time": timestamp,
                    "type": "metric_anomaly",
                    "label": f"{metric.get('name', 'Metric')} spike detected",
                    "color": "#ffd43b",
                    "icon": "trending-up",
                    "severity": "medium",
                    "metric_name": metric.get("name", ""),
                    "value": latest,
                    "unit": metric.get("unit", "")
                })

    def _add_change_events(self, changes: List[Dict[str, Any]]):
        """Add deployment/change events to timeline"""
        for change in changes[:5]:
            change_type = change.get("type", "change")
            color_map = {
                "deployment": "#51cf66",
                "config_change": "#339af0",
                "rollback": "#ff6b6b",
                "scale_event": "#ffd43b"
            }

            self.events.append({
                "time": change.get("timestamp", ""),
                "type": f"change_{change_type}",
                "label": f"{change_type}: {change.get('description', change.get('id', ''))}",
                "color": color_map.get(change_type, "#868e96"),
                "icon": "git-commit",
                "severity": "info",
                "change_id": change.get("id", ""),
                "service": change.get("service", "unknown")
            })

    def _add_rca_events(self, rca_results: Dict[str, Any], incident_time: str):
        """Add RCA completion events"""
        # RCA completion event
        if "execution_time_ms" in rca_results:
            exec_time_ms = rca_results["execution_time_ms"]
            exec_time_sec = exec_time_ms / 1000

            # Calculate RCA completion time (incident time + execution time)
            try:
                incident_dt = datetime.fromisoformat(incident_time.replace('Z', '+00:00'))
                rca_complete_dt = incident_dt + timedelta(seconds=exec_time_sec)
                rca_complete_time = rca_complete_dt.isoformat()
            except Exception:
                rca_complete_time = incident_time

            self.events.append({
                "time": rca_complete_time,
                "type": "rca_complete",
                "label": f"RCA Completed ({exec_time_sec:.2f}s)",
                "color": "#51cf66",
                "icon": "check-circle",
                "severity": "info"
            })

    def _to_plotly(self) -> Dict[str, Any]:
        """Convert to Plotly timeline format"""
        # Prepare data for Plotly timeline (scatter plot)
        times = []
        labels = []
        colors = []
        markers = []

        for event in self.events:
            times.append(event["time"])
            labels.append(event["label"])
            colors.append(event["color"])
            markers.append(event.get("icon", "circle"))

        return {
            "data": [{
                "type": "scatter",
                "mode": "markers+text",
                "x": times,
                "y": [1] * len(times),  # All on same horizontal line
                "text": labels,
                "textposition": "top center",
                "marker": {
                    "size": 15,
                    "color": colors,
                    "line": {"width": 2, "color": "#ffffff"}
                },
                "hovertemplate": "%{text}<br>%{x}<extra></extra>"
            }],
            "layout": {
                "title": "Incident Timeline",
                "xaxis": {"title": "Time"},
                "yaxis": {"visible": False},
                "showlegend": False,
                "height": 400
            }
        }

    def _to_chartjs(self) -> Dict[str, Any]:
        """Convert to Chart.js format"""
        labels = [event["time"] for event in self.events]
        data = [idx + 1 for idx in range(len(self.events))]
        colors = [event["color"] for event in self.events]

        return {
            "type": "line",
            "data": {
                "labels": labels,
                "datasets": [{
                    "label": "Timeline Events",
                    "data": data,
                    "borderColor": colors,
                    "backgroundColor": colors,
                    "pointRadius": 8,
                    "pointHoverRadius": 12
                }]
            },
            "options": {
                "responsive": True,
                "plugins": {
                    "legend": {"display": False},
                    "title": {
                        "display": True,
                        "text": "Incident Timeline"
                    }
                }
            }
        }

    def _to_d3_timeline(self) -> Dict[str, List]:
        """Convert to D3.js timeline format"""
        return {
            "events": [
                {
                    "date": event["time"],
                    "label": event["label"],
                    "type": event["type"],
                    "color": event["color"],
                    "icon": event.get("icon", "circle"),
                    "severity": event.get("severity", "info")
                }
                for event in self.events
            ]
        }

    def _to_gantt(self) -> Dict[str, Any]:
        """Convert to Gantt chart format (for agent execution visualization)"""
        # Group events by type to create gantt bars
        task_groups = {}

        for event in self.events:
            event_type = event["type"]
            if event_type not in task_groups:
                task_groups[event_type] = []
            task_groups[event_type].append(event)

        tasks = []
        for task_type, events in task_groups.items():
            if events:
                start_time = events[0]["time"]
                end_time = events[-1]["time"] if len(events) > 1 else start_time

                tasks.append({
                    "task": task_type.replace("_", " ").title(),
                    "start": start_time,
                    "end": end_time,
                    "color": events[0]["color"]
                })

        return {"tasks": tasks}

    def _get_stats(self) -> Dict[str, Any]:
        """Get timeline statistics"""
        if not self.events:
            return {"total_events": 0}

        # Count events by type
        type_counts = {}
        severity_counts = {}

        for event in self.events:
            event_type = event["type"]
            severity = event.get("severity", "unknown")

            type_counts[event_type] = type_counts.get(event_type, 0) + 1
            severity_counts[severity] = severity_counts.get(severity, 0) + 1

        # Calculate time span
        try:
            first_time = datetime.fromisoformat(self.events[0]["time"].replace('Z', '+00:00'))
            last_time = datetime.fromisoformat(self.events[-1]["time"].replace('Z', '+00:00'))
            duration_seconds = (last_time - first_time).total_seconds()
        except Exception:
            duration_seconds = 0

        return {
            "total_events": len(self.events),
            "event_types": type_counts,
            "severity_distribution": severity_counts,
            "duration_seconds": duration_seconds,
            "first_event": self.events[0]["time"],
            "last_event": self.events[-1]["time"]
        }
