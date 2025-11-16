"""
FastAPI server for ADAPT-Agents
Provides REST API for agent execution
"""

from fastapi import FastAPI, BackgroundTasks, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import uuid
import asyncio


# Create FastAPI app
app = FastAPI(
    title="ADAPT-Agents API",
    description="REST API for modular diagnostic agents",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Results store (use Redis in production)
results_store: Dict[str, Dict[str, Any]] = {}


# === Request/Response Models ===

class AnalysisRequest(BaseModel):
    """Request to start analysis"""
    incident_data: Dict[str, Any]
    agents: Optional[List[str]] = None
    parameters: Optional[Dict[str, Any]] = None
    callback_url: Optional[str] = None


class AnalysisResponse(BaseModel):
    """Response for created analysis"""
    analysis_id: str
    status: str
    status_url: str


class AgentExecutionRequest(BaseModel):
    """Request to execute single agent"""
    context: Dict[str, Any]
    parameters: Optional[Dict[str, Any]] = {}


# === API Endpoints ===

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "ADAPT-Agents API",
        "version": "2.0.0",
        "endpoints": {
            "analyze": "/analyze",
            "agent": "/agents/{agent_name}/execute",
            "status": "/analyze/{analysis_id}",
            "health": "/health",
            "metrics": "/metrics"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": "2.0.0"
    }


@app.post("/analyze", response_model=AnalysisResponse)
async def create_analysis(
    request: AnalysisRequest,
    background_tasks: BackgroundTasks
):
    """
    Start asynchronous RCA analysis

    Creates an analysis job and returns immediately with job ID.
    Results can be retrieved via /analyze/{analysis_id}
    """
    analysis_id = str(uuid.uuid4())

    # Initialize result
    results_store[analysis_id] = {
        "status": "queued",
        "created_at": str(asyncio.get_event_loop().time()),
        "results": None,
        "error": None
    }

    # Queue analysis as background task
    background_tasks.add_task(
        run_analysis,
        analysis_id,
        request.incident_data,
        request.agents,
        request.callback_url
    )

    return AnalysisResponse(
        analysis_id=analysis_id,
        status="queued",
        status_url=f"/analyze/{analysis_id}"
    )


@app.get("/analyze/{analysis_id}")
async def get_analysis(analysis_id: str):
    """
    Get analysis results

    Returns current status and results if complete
    """
    if analysis_id not in results_store:
        raise HTTPException(status_code=404, detail="Analysis not found")

    return results_store[analysis_id]


@app.post("/agents/{agent_name}/execute")
async def execute_agent(agent_name: str, request: AgentExecutionRequest):
    """
    Execute a single agent

    Synchronous execution of individual agent
    """
    from agents import (
        LogAnalyzerAgent, MetricsAnalyzerAgent, ChangeCorrelatorAgent,
        TopologyInferenceAgent, HypothesisGeneratorAgent, RemediationPlannerAgent
    )
    from schemas import BaseAgentInput

    agent_map = {
        "log": LogAnalyzerAgent,
        "metrics": MetricsAnalyzerAgent,
        "change": ChangeCorrelatorAgent,
        "topology": TopologyInferenceAgent,
        "hypothesis": HypothesisGeneratorAgent,
        "remediation": RemediationPlannerAgent
    }

    if agent_name not in agent_map:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")

    # Initialize agent
    agent_class = agent_map[agent_name]
    agent = agent_class()

    # Prepare input
    input_data = BaseAgentInput(
        context=request.context,
        parameters=request.parameters
    )

    # Execute
    try:
        result = agent.execute(input_data)
        return result.dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/agents")
async def list_agents():
    """List available agents"""
    return {
        "agents": [
            {
                "name": "log",
                "description": "Analyzes logs for error patterns and anomalies"
            },
            {
                "name": "metrics",
                "description": "Analyzes metrics for anomalies and threshold violations"
            },
            {
                "name": "change",
                "description": "Correlates changes with incidents"
            },
            {
                "name": "topology",
                "description": "Infers service dependencies from traces"
            },
            {
                "name": "hypothesis",
                "description": "Generates root cause hypotheses"
            },
            {
                "name": "remediation",
                "description": "Creates remediation plans"
            }
        ]
    }


# === Background Tasks ===

async def run_analysis(
    analysis_id: str,
    incident_data: Dict[str, Any],
    agents: Optional[List[str]],
    callback_url: Optional[str]
):
    """Run analysis in background"""
    try:
        # Update status
        results_store[analysis_id]["status"] = "running"

        # Import here to avoid circular dependency
        from chains.orchestrator import AgentOrchestrator

        # Execute
        orchestrator = AgentOrchestrator(error_strategy="continue")
        results = orchestrator.execute_rca_chain(incident_data)

        # Store results (convert to dict for JSON serialization)
        results_store[analysis_id]["status"] = "completed"
        results_store[analysis_id]["results"] = _serialize_results(results)

        # Call webhook if provided
        if callback_url:
            await _send_callback(callback_url, analysis_id, results)

    except Exception as e:
        results_store[analysis_id]["status"] = "failed"
        results_store[analysis_id]["error"] = str(e)


def _serialize_results(results: Dict) -> Dict:
    """Serialize results for JSON response"""
    serialized = {}

    for key, value in results.items():
        if hasattr(value, 'dict'):
            serialized[key] = value.dict()
        elif isinstance(value, dict):
            serialized[key] = {
                k: v.dict() if hasattr(v, 'dict') else v
                for k, v in value.items()
            }
        else:
            serialized[key] = value

    return serialized


async def _send_callback(url: str, analysis_id: str, results: Dict):
    """Send callback webhook"""
    import httpx

    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                url,
                json={
                    "analysis_id": analysis_id,
                    "status": "completed",
                    "results": results
                },
                timeout=30
            )
    except Exception:
        # Log but don't fail
        pass


# === Startup/Shutdown ===

@app.on_event("startup")
async def startup_event():
    """Initialize on startup"""
    # Start metrics server if enabled
    from config.settings import get_settings
    settings = get_settings()

    if settings.metrics_enabled:
        from utils.metrics import start_metrics_server
        start_metrics_server(settings.metrics_port)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
