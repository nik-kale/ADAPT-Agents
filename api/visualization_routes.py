"""
Visualization API Routes
Provides endpoints for generating interactive visualizations of RCA data
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, Optional, List, Any

from visualization import RootCauseGraphGenerator, TimelineChartGenerator, MetricsDashboardGenerator
from api.auth import get_api_key


router = APIRouter()


# Pydantic models
class RCAVisualizationRequest(BaseModel):
    """Request to generate RCA visualization"""
    rca_results: Dict[str, Any]
    format: Optional[str] = "all"  # all, cytoscape, d3, graphml, dot


class TimelineRequest(BaseModel):
    """Request to generate timeline"""
    incident_data: Dict[str, Any]
    rca_results: Optional[Dict[str, Any]] = None
    format: Optional[str] = "all"  # all, plotly, chartjs, d3, gantt


class MetricsDashboardRequest(BaseModel):
    """Request to generate metrics dashboard"""
    metrics: List[Dict[str, Any]]
    incident_time: Optional[str] = None
    format: Optional[str] = "all"  # all, plotly, chartjs


@router.post("/visualizations/root-cause-graph", tags=["visualizations"])
async def generate_root_cause_graph(
    request: RCAVisualizationRequest,
    api_key: str = Depends(get_api_key)
):
    """
    Generate interactive root cause dependency graph

    Creates a graph showing relationships between:
    - Incident
    - Services
    - Findings from agents
    - Hypotheses
    - Remediation actions

    Supports multiple export formats:
    - Cytoscape.js (interactive web visualization)
    - D3.js (force-directed graph)
    - GraphML (standard graph format)
    - DOT (Graphviz format)

    Example:
    ```json
    {
        "rca_results": {...},
        "format": "cytoscape"
    }
    ```
    """
    try:
        generator = RootCauseGraphGenerator()
        graph_data = generator.generate_from_rca(request.rca_results)

        # Filter by requested format
        if request.format != "all":
            if request.format in graph_data:
                return {
                    "format": request.format,
                    "data": graph_data[request.format],
                    "stats": graph_data["stats"]
                }
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid format: {request.format}. Available: cytoscape, d3, graphml, dot, all"
                )

        return {
            "formats": ["nodes", "edges", "cytoscape", "d3", "graphml", "dot"],
            "data": graph_data
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate root cause graph: {str(e)}"
        )


@router.post("/visualizations/timeline", tags=["visualizations"])
async def generate_timeline(
    request: TimelineRequest,
    api_key: str = Depends(get_api_key)
):
    """
    Generate interactive incident timeline

    Creates a timeline showing:
    - Incident start
    - Error log events
    - Warning log events
    - Metric anomalies
    - Deployment/change events
    - RCA completion

    Supports multiple formats:
    - Plotly (interactive charts)
    - Chart.js (canvas-based charts)
    - D3.js (custom SVG timeline)
    - Gantt (for agent execution visualization)

    Example:
    ```json
    {
        "incident_data": {
            "incident_time": "2025-01-15T10:00:00Z",
            "logs": [...],
            "metrics": [...],
            "changes": [...]
        },
        "format": "plotly"
    }
    ```
    """
    try:
        generator = TimelineChartGenerator()
        timeline_data = generator.generate_from_incident(
            request.incident_data,
            request.rca_results
        )

        # Filter by requested format
        if request.format != "all":
            if request.format in timeline_data:
                return {
                    "format": request.format,
                    "data": timeline_data[request.format],
                    "stats": timeline_data["stats"]
                }
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid format: {request.format}. Available: plotly, chartjs, d3_timeline, gantt, all"
                )

        return {
            "formats": ["events", "plotly", "chartjs", "d3_timeline", "gantt"],
            "data": timeline_data
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate timeline: {str(e)}"
        )


@router.post("/visualizations/metrics-dashboard", tags=["visualizations"])
async def generate_metrics_dashboard(
    request: MetricsDashboardRequest,
    api_key: str = Depends(get_api_key)
):
    """
    Generate interactive metrics dashboard

    Creates visualizations for:
    - Individual metric time-series
    - Anomaly detection and highlighting
    - Correlation heatmap
    - Summary statistics panel

    Supports formats:
    - Plotly (multi-plot dashboard)
    - Chart.js (individual charts)

    Example:
    ```json
    {
        "metrics": [
            {
                "name": "cpu_usage",
                "service": "api-service",
                "values": [45, 50, 55, 85, 90],
                "unit": "%"
            }
        ],
        "incident_time": "2025-01-15T10:00:00Z",
        "format": "plotly"
    }
    ```
    """
    try:
        generator = MetricsDashboardGenerator()
        dashboard_data = generator.generate_from_metrics(
            request.metrics,
            request.incident_time
        )

        # Filter by requested format
        if request.format != "all":
            format_key = f"{request.format}_dashboard"
            if format_key in dashboard_data:
                return {
                    "format": request.format,
                    "data": dashboard_data[format_key],
                    "stats": dashboard_data["stats"],
                    "anomalies": dashboard_data["anomalies"]
                }
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid format: {request.format}. Available: plotly, chartjs, all"
                )

        return {
            "formats": ["charts", "heatmap", "summary", "plotly_dashboard", "chartjs_dashboard"],
            "data": dashboard_data
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate metrics dashboard: {str(e)}"
        )


@router.post("/visualizations/complete-dashboard", tags=["visualizations"])
async def generate_complete_dashboard(
    incident_data: Dict[str, Any],
    rca_results: Dict[str, Any],
    api_key: str = Depends(get_api_key)
):
    """
    Generate complete visualization dashboard for an incident

    Creates all visualizations in one call:
    - Root cause dependency graph
    - Incident timeline
    - Metrics dashboard
    - Summary statistics

    This is a convenience endpoint that combines all visualization types.

    Example:
    ```json
    {
        "incident_data": {...},
        "rca_results": {...}
    }
    ```
    """
    try:
        # Generate root cause graph
        graph_generator = RootCauseGraphGenerator()
        graph_data = graph_generator.generate_from_rca(rca_results)

        # Generate timeline
        timeline_generator = TimelineChartGenerator()
        timeline_data = timeline_generator.generate_from_incident(
            incident_data,
            rca_results
        )

        # Generate metrics dashboard (if metrics available)
        dashboard_data = None
        if "metrics" in incident_data and incident_data["metrics"]:
            dashboard_generator = MetricsDashboardGenerator()
            dashboard_data = dashboard_generator.generate_from_metrics(
                incident_data["metrics"],
                incident_data.get("incident_time")
            )

        return {
            "root_cause_graph": {
                "cytoscape": graph_data["cytoscape"],
                "d3": graph_data["d3"],
                "stats": graph_data["stats"]
            },
            "timeline": {
                "plotly": timeline_data["plotly"],
                "events": timeline_data["events"],
                "stats": timeline_data["stats"]
            },
            "metrics_dashboard": dashboard_data if dashboard_data else {
                "available": False,
                "reason": "No metrics in incident data"
            },
            "summary": {
                "total_visualizations": 3 if dashboard_data else 2,
                "formats_available": ["cytoscape", "d3", "plotly", "chartjs"]
            }
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate complete dashboard: {str(e)}"
        )


@router.get("/visualizations/formats", tags=["visualizations"])
async def list_supported_formats():
    """
    List all supported visualization formats

    Returns information about available formats for each visualization type.
    """
    return {
        "root_cause_graph": {
            "formats": ["cytoscape", "d3", "graphml", "dot"],
            "descriptions": {
                "cytoscape": "Cytoscape.js format (interactive web)",
                "d3": "D3.js force-directed graph",
                "graphml": "GraphML standard format",
                "dot": "Graphviz DOT format"
            }
        },
        "timeline": {
            "formats": ["plotly", "chartjs", "d3_timeline", "gantt"],
            "descriptions": {
                "plotly": "Plotly interactive charts",
                "chartjs": "Chart.js canvas charts",
                "d3_timeline": "D3.js custom timeline",
                "gantt": "Gantt chart for tasks"
            }
        },
        "metrics_dashboard": {
            "formats": ["plotly", "chartjs"],
            "descriptions": {
                "plotly": "Plotly multi-plot dashboard",
                "chartjs": "Chart.js individual charts"
            }
        }
    }
