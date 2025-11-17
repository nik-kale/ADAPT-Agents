"""
FastAPI server for ADAPT-Agents v3.2
Provides REST API for agent execution with:
- AsyncAgentOrchestrator (parallel execution)
- WebSocket support for real-time streaming
- API key authentication
- Rate limiting
- Request ID tracking
- Database backend (SQLite)
- Graceful shutdown
- Configuration validation
"""

from fastapi import FastAPI, BackgroundTasks, HTTPException, Depends, Security, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from fastapi.responses import JSONResponse
from pydantic import BaseModel, validator
from typing import Dict, Any, List, Optional
import uuid
import asyncio
import time
import sqlite3
import json
import signal
import sys
from datetime import datetime
from collections import defaultdict
from contextlib import asynccontextmanager

# Import WebSocket routes
try:
    from api.websocket_routes import router as websocket_router
    from api.websocket_manager import manager as ws_manager
    WEBSOCKET_AVAILABLE = True
except ImportError:
    WEBSOCKET_AVAILABLE = False

# Import Webhook routes
try:
    from api.webhook_routes import router as webhook_router
    from api.webhook_manager import webhook_manager
    WEBHOOK_AVAILABLE = True
except ImportError:
    WEBHOOK_AVAILABLE = False


# === Configuration ===

# Rate limiting configuration
RATE_LIMIT_REQUESTS = 100  # requests per minute per API key
RATE_LIMIT_WINDOW = 60  # seconds

# API Key configuration (in production, use environment variables or secrets manager)
VALID_API_KEYS = {
    "demo-key-12345": {"name": "demo", "tier": "free"},
    "prod-key-67890": {"name": "production", "tier": "premium"}
}

# Database configuration
DB_PATH = "adapt_agents.db"


# === Database Setup ===

def init_database():
    """Initialize SQLite database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Create analyses table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS analyses (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            status TEXT NOT NULL,
            api_key TEXT,
            incident_data TEXT,
            results TEXT,
            error TEXT,
            completed_at TEXT
        )
    """)

    # Create agent_executions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS agent_executions (
            id TEXT PRIMARY KEY,
            analysis_id TEXT,
            agent_name TEXT NOT NULL,
            created_at TEXT NOT NULL,
            execution_time_ms REAL,
            status TEXT NOT NULL,
            findings_count INTEGER,
            FOREIGN KEY (analysis_id) REFERENCES analyses(id)
        )
    """)

    # Create indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_analyses_status ON analyses(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_analyses_created_at ON analyses(created_at)")

    conn.commit()
    conn.close()


# === Rate Limiting ===

class RateLimiter:
    """Simple in-memory rate limiter"""

    def __init__(self):
        self.requests = defaultdict(list)

    def is_allowed(self, api_key: str) -> bool:
        """Check if request is allowed under rate limit"""
        now = time.time()

        # Clean old requests
        self.requests[api_key] = [
            req_time for req_time in self.requests[api_key]
            if now - req_time < RATE_LIMIT_WINDOW
        ]

        # Check limit
        if len(self.requests[api_key]) >= RATE_LIMIT_REQUESTS:
            return False

        # Add new request
        self.requests[api_key].append(now)
        return True

    def get_remaining(self, api_key: str) -> int:
        """Get remaining requests in current window"""
        now = time.time()
        active_requests = [
            req_time for req_time in self.requests[api_key]
            if now - req_time < RATE_LIMIT_WINDOW
        ]
        return max(0, RATE_LIMIT_REQUESTS - len(active_requests))


rate_limiter = RateLimiter()


# === Lifespan Context Manager ===

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup and shutdown"""
    # Startup
    print("🚀 Starting ADAPT-Agents API v3.0...")

    # Initialize database
    init_database()
    print("✓ Database initialized")

    # Validate configuration
    from config.settings import get_settings
    try:
        settings = get_settings()
        print(f"✓ Configuration validated (LLM: {settings.llm_provider}, Cache: {settings.cache_backend})")
    except Exception as e:
        print(f"⚠️  Configuration warning: {e}")

    # Start metrics server if enabled
    try:
        if settings.metrics_enabled:
            from utils.metrics import start_metrics_server
            start_metrics_server(settings.metrics_port)
            print(f"✓ Metrics server started on port {settings.metrics_port}")
    except Exception as e:
        print(f"⚠️  Metrics server warning: {e}")

    print("✅ API server ready")

    yield

    # Shutdown
    print("\n🛑 Shutting down gracefully...")

    # Close database connections, cleanup resources, etc.
    # (SQLite auto-closes, but you could add cleanup here)

    print("✅ Shutdown complete")


# === Create FastAPI App ===

app = FastAPI(
    title="ADAPT-Agents API",
    description="REST API for modular diagnostic agents with async execution, real-time streaming, authentication, and rate limiting",
    version="3.2.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Include WebSocket routes
if WEBSOCKET_AVAILABLE:
    app.include_router(websocket_router, tags=["websockets"])

# Include Webhook routes
if WEBHOOK_AVAILABLE:
    app.include_router(webhook_router, prefix="/api/v1", tags=["webhooks"])

# === Middleware ===

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request ID middleware
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Add request ID to all requests"""
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id

    return response


# === Authentication ===

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def get_api_key(api_key: str = Security(api_key_header)) -> str:
    """Validate API key"""
    if not api_key or api_key not in VALID_API_KEYS:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key. Provide X-API-Key header."
        )

    # Check rate limit
    if not rate_limiter.is_allowed(api_key):
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Limit: {RATE_LIMIT_REQUESTS} requests per {RATE_LIMIT_WINDOW}s"
        )

    return api_key


# === Database Operations ===

class DatabaseOperations:
    """Database operations for analyses"""

    @staticmethod
    def create_analysis(analysis_id: str, incident_data: Dict, api_key: str):
        """Create new analysis record"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO analyses (id, created_at, status, api_key, incident_data)
            VALUES (?, ?, ?, ?, ?)
        """, (
            analysis_id,
            datetime.utcnow().isoformat(),
            "queued",
            api_key,
            json.dumps(incident_data)
        ))

        conn.commit()
        conn.close()

    @staticmethod
    def update_analysis_status(analysis_id: str, status: str, results: Optional[Dict] = None, error: Optional[str] = None):
        """Update analysis status"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        if status == "completed":
            cursor.execute("""
                UPDATE analyses
                SET status = ?, results = ?, completed_at = ?
                WHERE id = ?
            """, (status, json.dumps(results) if results else None, datetime.utcnow().isoformat(), analysis_id))
        elif status == "failed":
            cursor.execute("""
                UPDATE analyses
                SET status = ?, error = ?, completed_at = ?
                WHERE id = ?
            """, (status, error, datetime.utcnow().isoformat(), analysis_id))
        else:
            cursor.execute("""
                UPDATE analyses
                SET status = ?
                WHERE id = ?
            """, (status, analysis_id))

        conn.commit()
        conn.close()

    @staticmethod
    def get_analysis(analysis_id: str) -> Optional[Dict]:
        """Get analysis by ID"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, created_at, status, results, error, completed_at
            FROM analyses
            WHERE id = ?
        """, (analysis_id,))

        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return {
            "analysis_id": row[0],
            "created_at": row[1],
            "status": row[2],
            "results": json.loads(row[3]) if row[3] else None,
            "error": row[4],
            "completed_at": row[5]
        }

    @staticmethod
    def save_agent_execution(analysis_id: str, agent_name: str, execution_time_ms: float, status: str, findings_count: int):
        """Save agent execution metrics"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO agent_executions (id, analysis_id, agent_name, created_at, execution_time_ms, status, findings_count)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            str(uuid.uuid4()),
            analysis_id,
            agent_name,
            datetime.utcnow().isoformat(),
            execution_time_ms,
            status,
            findings_count
        ))

        conn.commit()
        conn.close()


db = DatabaseOperations()


# === Request/Response Models ===

class AnalysisRequest(BaseModel):
    """Request to start analysis"""
    incident_data: Dict[str, Any]
    agents: Optional[List[str]] = None
    parameters: Optional[Dict[str, Any]] = None
    callback_url: Optional[str] = None
    use_llm: bool = False
    filter_pii: bool = False

    @validator('incident_data')
    def validate_incident_data(cls, v):
        """Validate incident data has required fields"""
        if not v:
            raise ValueError("incident_data cannot be empty")
        return v


class AnalysisResponse(BaseModel):
    """Response for created analysis"""
    analysis_id: str
    status: str
    status_url: str
    request_id: str


class AgentExecutionRequest(BaseModel):
    """Request to execute single agent"""
    context: Dict[str, Any]
    parameters: Optional[Dict[str, Any]] = {}
    use_llm: bool = False


# === API Endpoints ===

@app.get("/")
async def root(request: Request):
    """Root endpoint"""
    endpoints = {
        "analyze": "/analyze",
        "agent": "/agents/{agent_name}/execute",
        "status": "/analyze/{analysis_id}",
        "agents": "/agents",
        "health": "/health",
        "stats": "/stats",
        "metrics": "Prometheus metrics on port 9090 (if enabled)"
    }

    if WEBSOCKET_AVAILABLE:
        endpoints["websocket_analysis"] = "ws://host/ws/analysis/{analysis_id}"
        endpoints["websocket_broadcast"] = "ws://host/ws/broadcast"
        endpoints["websocket_agent"] = "ws://host/ws/agent/{agent_name}"

    return {
        "name": "ADAPT-Agents API",
        "version": "3.2.0",
        "features": [
            "Async/Await execution",
            "Real-time WebSocket streaming" if WEBSOCKET_AVAILABLE else "WebSocket support (install websockets)",
            "LLM integration (OpenAI/Anthropic)",
            "PII filtering",
            "Result caching",
            "Prometheus metrics",
            "API key authentication",
            "Rate limiting",
            "Request tracking",
            "Database persistence"
        ],
        "endpoints": endpoints,
        "request_id": request.state.request_id
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    # Check database connection
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.close()
        db_healthy = True
    except Exception:
        db_healthy = False

    return {
        "status": "healthy" if db_healthy else "degraded",
        "version": "3.0.0",
        "database": "healthy" if db_healthy else "unhealthy"
    }


@app.post("/analyze", response_model=AnalysisResponse)
async def create_analysis(
    request: Request,
    analysis_request: AnalysisRequest,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(get_api_key)
):
    """
    Start asynchronous RCA analysis

    Creates an analysis job and returns immediately with job ID.
    Results can be retrieved via /analyze/{analysis_id}

    Requires X-API-Key header for authentication.
    """
    analysis_id = str(uuid.uuid4())
    request_id = request.state.request_id

    # Save to database
    db.create_analysis(analysis_id, analysis_request.incident_data, api_key)

    # Queue analysis as background task
    background_tasks.add_task(
        run_analysis,
        analysis_id,
        analysis_request.incident_data,
        analysis_request.agents,
        analysis_request.callback_url,
        analysis_request.use_llm,
        analysis_request.filter_pii
    )

    return AnalysisResponse(
        analysis_id=analysis_id,
        status="queued",
        status_url=f"/analyze/{analysis_id}",
        request_id=request_id
    )


@app.get("/analyze/{analysis_id}")
async def get_analysis(
    analysis_id: str,
    api_key: str = Depends(get_api_key)
):
    """
    Get analysis results

    Returns current status and results if complete.
    Requires X-API-Key header for authentication.
    """
    result = db.get_analysis(analysis_id)

    if not result:
        raise HTTPException(status_code=404, detail="Analysis not found")

    # Add rate limit info
    result["rate_limit_remaining"] = rate_limiter.get_remaining(api_key)

    return result


@app.post("/agents/{agent_name}/execute")
async def execute_agent(
    agent_name: str,
    execution_request: AgentExecutionRequest,
    api_key: str = Depends(get_api_key)
):
    """
    Execute a single agent

    Synchronous execution of individual agent.
    Requires X-API-Key header for authentication.
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
    agent = agent_class(use_llm=execution_request.use_llm)

    # Prepare input
    input_data = BaseAgentInput(
        context=execution_request.context,
        parameters=execution_request.parameters
    )

    # Execute async
    try:
        result = await agent.execute_async(input_data)
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
                "description": "Analyzes logs for error patterns and anomalies",
                "supports_llm": True,
                "supports_caching": True
            },
            {
                "name": "metrics",
                "description": "Analyzes metrics for anomalies and threshold violations",
                "supports_llm": True,
                "supports_caching": True
            },
            {
                "name": "change",
                "description": "Correlates changes with incidents",
                "supports_llm": True,
                "supports_caching": True
            },
            {
                "name": "topology",
                "description": "Infers service dependencies from traces",
                "supports_llm": True,
                "supports_caching": True
            },
            {
                "name": "hypothesis",
                "description": "Generates root cause hypotheses",
                "supports_llm": True,
                "supports_caching": True
            },
            {
                "name": "remediation",
                "description": "Creates remediation plans",
                "supports_llm": True,
                "supports_caching": True
            }
        ]
    }


@app.get("/stats")
async def get_stats(api_key: str = Depends(get_api_key)):
    """Get API statistics"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Total analyses
    cursor.execute("SELECT COUNT(*) FROM analyses")
    total_analyses = cursor.fetchone()[0]

    # Analyses by status
    cursor.execute("SELECT status, COUNT(*) FROM analyses GROUP BY status")
    status_counts = dict(cursor.fetchall())

    # Average execution time
    cursor.execute("SELECT AVG(execution_time_ms) FROM agent_executions WHERE status = 'completed'")
    avg_execution_time = cursor.fetchone()[0] or 0

    conn.close()

    return {
        "total_analyses": total_analyses,
        "status_counts": status_counts,
        "avg_execution_time_ms": round(avg_execution_time, 2),
        "rate_limit_remaining": rate_limiter.get_remaining(api_key)
    }


# === Background Tasks ===

async def run_analysis(
    analysis_id: str,
    incident_data: Dict[str, Any],
    agents: Optional[List[str]],
    callback_url: Optional[str],
    use_llm: bool = False,
    filter_pii: bool = False
):
    """Run analysis in background using AsyncAgentOrchestrator with optional streaming"""
    try:
        # Update status
        db.update_analysis_status(analysis_id, "running")

        # Use StreamingOrchestrator if WebSocket available, otherwise standard AsyncAgentOrchestrator
        if WEBSOCKET_AVAILABLE:
            from chains.streaming_orchestrator import StreamingOrchestrator
            orchestrator = StreamingOrchestrator(
                websocket_manager=ws_manager,
                analysis_id=analysis_id,
                error_strategy="continue",
                use_llm=use_llm,
                filter_pii=filter_pii
            )
        else:
            from chains.async_orchestrator import AsyncAgentOrchestrator
            orchestrator = AsyncAgentOrchestrator(
                error_strategy="continue",
                use_llm=use_llm,
                filter_pii=filter_pii
            )

        results = await orchestrator.execute_rca_chain(incident_data)

        # Store results
        serialized_results = _serialize_results(results)
        db.update_analysis_status(analysis_id, "completed", serialized_results)

        # Save agent execution metrics
        for phase, phase_results in results.items():
            if isinstance(phase_results, dict):
                for agent_name, agent_result in phase_results.items():
                    if hasattr(agent_result, 'execution_time_ms'):
                        db.save_agent_execution(
                            analysis_id,
                            agent_name,
                            agent_result.execution_time_ms,
                            agent_result.status.value if hasattr(agent_result.status, 'value') else str(agent_result.status),
                            len(agent_result.findings) if hasattr(agent_result, 'findings') else 0
                        )

        # Call webhook if provided
        if callback_url:
            await _send_callback(callback_url, analysis_id, serialized_results)

    except Exception as e:
        db.update_analysis_status(analysis_id, "failed", error=str(e))


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


# === Graceful Shutdown Handler ===

def signal_handler(sig, frame):
    """Handle shutdown signals"""
    print(f"\n⚠️  Received signal {sig}, shutting down gracefully...")
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
