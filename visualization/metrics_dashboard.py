"""
Metrics Dashboard Generator
Creates interactive metric visualizations and anomaly highlights
"""

from typing import Dict, Any, List, Optional
import json


class MetricsDashboardGenerator:
    """
    Generates interactive metrics dashboards

    Features:
    - Time-series metric charts
    - Anomaly highlighting
    - Multi-metric comparison
    - Threshold visualization
    - Heatmap for correlated metrics
    - Exportable to Plotly, Chart.js, D3.js formats
    """

    def __init__(self):
        """Initialize metrics dashboard generator"""
        pass

    def generate_from_metrics(
        self,
        metrics: List[Dict[str, Any]],
        incident_time: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate metrics dashboard from metric data

        Args:
            metrics: List of metric data
            incident_time: Optional incident timestamp to mark

        Returns:
            Dashboard data in multiple formats
        """
        return {
            "charts": self._create_individual_charts(metrics, incident_time),
            "heatmap": self._create_correlation_heatmap(metrics),
            "summary": self._create_summary_panel(metrics),
            "anomalies": self._detect_anomalies(metrics),
            "plotly_dashboard": self._to_plotly_dashboard(metrics, incident_time),
            "chartjs_dashboard": self._to_chartjs_dashboard(metrics),
            "stats": self._get_stats(metrics)
        }

    def _create_individual_charts(
        self,
        metrics: List[Dict[str, Any]],
        incident_time: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Create individual charts for each metric"""
        charts = []

        for metric in metrics:
            chart_data = {
                "metric_name": metric.get("name", "Unknown"),
                "service": metric.get("service", "Unknown"),
                "unit": metric.get("unit", ""),
                "values": metric.get("values", []),
                "timestamps": metric.get("timestamps", []),
                "incident_marked": bool(incident_time),
                "chart_type": "line"
            }

            # Detect anomalies in this metric
            anomaly_indices = self._detect_metric_anomalies(metric.get("values", []))
            chart_data["anomaly_indices"] = anomaly_indices

            charts.append(chart_data)

        return charts

    def _create_correlation_heatmap(self, metrics: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create correlation heatmap between metrics"""
        if len(metrics) < 2:
            return {"available": False, "reason": "Insufficient metrics"}

        # Extract metric names and values
        metric_names = []
        metric_values = []

        for metric in metrics:
            if "values" in metric and metric["values"]:
                metric_names.append(metric.get("name", "Unknown"))
                metric_values.append(metric["values"])

        # Compute correlation matrix (simplified - would use numpy in production)
        correlation_matrix = []
        for i, values_i in enumerate(metric_values):
            row = []
            for j, values_j in enumerate(metric_values):
                # Simple correlation approximation
                if i == j:
                    corr = 1.0
                else:
                    # Placeholder correlation (in production, use Pearson correlation)
                    corr = 0.0
                row.append(corr)
            correlation_matrix.append(row)

        return {
            "available": True,
            "metric_names": metric_names,
            "correlation_matrix": correlation_matrix,
            "note": "Correlation computation simplified - would use statistical methods in production"
        }

    def _create_summary_panel(self, metrics: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create summary statistics panel"""
        summaries = []

        for metric in metrics:
            values = metric.get("values", [])
            if not values:
                continue

            summary = {
                "metric_name": metric.get("name", "Unknown"),
                "current": values[-1] if values else None,
                "min": min(values),
                "max": max(values),
                "avg": sum(values) / len(values),
                "unit": metric.get("unit", ""),
                "service": metric.get("service", "Unknown")
            }

            # Calculate change percentage
            if len(values) >= 2:
                old_val = values[0]
                new_val = values[-1]
                if old_val != 0:
                    change_pct = ((new_val - old_val) / old_val) * 100
                    summary["change_percent"] = round(change_pct, 2)

            summaries.append(summary)

        return {"summaries": summaries}

    def _detect_anomalies(self, metrics: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Detect anomalies across all metrics"""
        anomalies = []

        for metric in metrics:
            values = metric.get("values", [])
            if not values:
                continue

            anomaly_indices = self._detect_metric_anomalies(values)

            if anomaly_indices:
                anomalies.append({
                    "metric_name": metric.get("name", "Unknown"),
                    "service": metric.get("service", "Unknown"),
                    "anomaly_count": len(anomaly_indices),
                    "anomaly_indices": anomaly_indices,
                    "severity": "high" if len(anomaly_indices) > 2 else "medium"
                })

        return anomalies

    def _detect_metric_anomalies(self, values: List[float]) -> List[int]:
        """
        Detect anomalies in metric values using simple threshold method

        Args:
            values: List of metric values

        Returns:
            List of indices where anomalies detected
        """
        if len(values) < 3:
            return []

        # Calculate mean and std dev
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        std_dev = variance ** 0.5

        # Detect values beyond 2 standard deviations
        anomaly_indices = []
        threshold = 2.0

        for idx, value in enumerate(values):
            if abs(value - mean) > threshold * std_dev:
                anomaly_indices.append(idx)

        return anomaly_indices

    def _to_plotly_dashboard(
        self,
        metrics: List[Dict[str, Any]],
        incident_time: Optional[str] = None
    ) -> Dict[str, Any]:
        """Convert to Plotly dashboard format with subplots"""
        traces = []
        shapes = []  # For incident marker

        for idx, metric in enumerate(metrics):
            values = metric.get("values", [])
            timestamps = metric.get("timestamps", list(range(len(values))))

            # Main metric trace
            traces.append({
                "type": "scatter",
                "mode": "lines+markers",
                "name": metric.get("name", "Metric"),
                "x": timestamps,
                "y": values,
                "yaxis": f"y{idx + 1}" if idx > 0 else "y",
                "marker": {"size": 6}
            })

            # Add anomaly markers
            anomaly_indices = self._detect_metric_anomalies(values)
            if anomaly_indices:
                anomaly_times = [timestamps[i] for i in anomaly_indices if i < len(timestamps)]
                anomaly_values = [values[i] for i in anomaly_indices if i < len(values)]

                traces.append({
                    "type": "scatter",
                    "mode": "markers",
                    "name": f"{metric.get('name')} Anomalies",
                    "x": anomaly_times,
                    "y": anomaly_values,
                    "yaxis": f"y{idx + 1}" if idx > 0 else "y",
                    "marker": {
                        "size": 12,
                        "color": "#ff0000",
                        "symbol": "x"
                    }
                })

        layout = {
            "title": "Metrics Dashboard",
            "grid": {"rows": len(metrics), "columns": 1, "pattern": "independent"},
            "height": 300 * len(metrics),
            "showlegend": True
        }

        return {
            "data": traces,
            "layout": layout
        }

    def _to_chartjs_dashboard(self, metrics: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert to Chart.js format (one chart per metric)"""
        charts = []

        for metric in metrics:
            values = metric.get("values", [])
            timestamps = metric.get("timestamps", list(range(len(values))))

            chart = {
                "type": "line",
                "data": {
                    "labels": timestamps,
                    "datasets": [{
                        "label": metric.get("name", "Metric"),
                        "data": values,
                        "borderColor": "#4285f4",
                        "backgroundColor": "rgba(66, 133, 244, 0.1)",
                        "tension": 0.4,
                        "pointRadius": 4,
                        "pointHoverRadius": 6
                    }]
                },
                "options": {
                    "responsive": True,
                    "plugins": {
                        "title": {
                            "display": True,
                            "text": f"{metric.get('name', 'Metric')} - {metric.get('service', '')}"
                        }
                    },
                    "scales": {
                        "y": {
                            "beginAtZero": False,
                            "title": {
                                "display": True,
                                "text": metric.get("unit", "")
                            }
                        }
                    }
                }
            }

            # Add anomaly points as separate dataset
            anomaly_indices = self._detect_metric_anomalies(values)
            if anomaly_indices:
                anomaly_data = [None] * len(values)
                for idx in anomaly_indices:
                    if idx < len(values):
                        anomaly_data[idx] = values[idx]

                chart["data"]["datasets"].append({
                    "label": "Anomalies",
                    "data": anomaly_data,
                    "borderColor": "#ff0000",
                    "backgroundColor": "#ff0000",
                    "pointRadius": 8,
                    "pointStyle": "crossRot",
                    "showLine": False
                })

            charts.append(chart)

        return charts

    def _get_stats(self, metrics: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Get metrics statistics"""
        total_values = sum(len(m.get("values", [])) for m in metrics)
        total_anomalies = sum(len(self._detect_metric_anomalies(m.get("values", []))) for m in metrics)

        metric_names = [m.get("name", "Unknown") for m in metrics]
        services = list(set(m.get("service", "Unknown") for m in metrics))

        return {
            "total_metrics": len(metrics),
            "total_data_points": total_values,
            "total_anomalies": total_anomalies,
            "metric_names": metric_names,
            "services": services
        }
