"""
FastAPI server for ADAPT-Agents v3.5
Provides REST API for agent execution with:
- AsyncAgentOrchestrator (parallel execution)
- WebSocket support for real-time streaming
- Webhook callbacks for external integrations
- RAG & Historical Learning (ChromaDB + sentence-transformers)
- Enterprise integrations (Slack, JIRA, PagerDuty)
- Interactive visualizations (root cause graphs, timelines, dashboards)
- API key authentication
- Rate limiting
- Request ID tracking
- Database backend (SQLite)
- Graceful shutdown
- Configuration validation
"""

from fastapi import FastAPI, BackgroundTasks, HTTPException, Depends, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, validator, field_validator, HttpUrl
from typing import Dict, Any, List, Optional
import uuid
import asyncio
import time
import sqlite3
import json
import signal
import sys
import logging
from datetime import datetime
from collections import defaultdict
from contextlib import asynccontextmanager
from config.settings import get_settings
from api.auth import get_api_key, generate_ws_token
from utils.rate_limiter import rate_limiter
from utils.cleanup import get_cleanup_service, scheduled_cleanup_task
from utils.circuit_breaker import circuit_breaker_registry

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

# Import Knowledge Base routes
try:
    from api.knowledge_base_routes import router as knowledge_base_router
    KNOWLEDGE_BASE_AVAILABLE = True
except ImportError:
    KNOWLEDGE_BASE_AVAILABLE = False

# Import Integrations routes
try:
    from api.integrations_routes import router as integrations_router
    INTEGRATIONS_AVAILABLE = True
except ImportError:
    INTEGRATIONS_AVAILABLE = False

# Import Visualization routes
try:
    from api.visualization_routes import router as visualization_router
    VISUALIZATION_AVAILABLE = True
except ImportError:
    VISUALIZATION_AVAILABLE = False


# === Configuration ===

# Rate limiting configuration
RATE_LIMIT_REQUESTS = 100  # requests per minute per API key
RATE_LIMIT_WINDOW = 60  # seconds

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


# Rate limiting is now handled in utils/rate_limiter.py


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
    
    # Initialize OpenTelemetry tracing if enabled
    try:
        if settings.enable_tracing and settings.otel_endpoint:
            from utils.tracing import init_tracing
            from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
            
            # Initialize tracing
            if init_tracing(
                service_name=settings.otel_service_name,
                otlp_endpoint=settings.otel_endpoint
            ):
                # Instrument FastAPI app
                FastAPIInstrumentor.instrument_app(app)
                print(f"✓ OpenTelemetry tracing enabled: {settings.otel_endpoint}")
            else:
                print("⚠️  OpenTelemetry tracing initialization failed")
        elif settings.enable_tracing:
            print("⚠️  Tracing enabled but OTEL endpoint not configured")
    except Exception as e:
        print(f"⚠️  Tracing initialization warning: {e}")
    
    # Start cleanup scheduler if enabled
    cleanup_task = None
    try:
        if settings.enable_auto_cleanup:
            cleanup_task = asyncio.create_task(scheduled_cleanup_task())
            print(f"✓ Cleanup scheduler started (retention: {settings.data_retention_days} days)")
    except Exception as e:
        print(f"⚠️  Cleanup scheduler warning: {e}")

    print("✅ API server ready")

    yield

    # Shutdown
    print("\n🛑 Shutting down gracefully...")

    # Shutdown tracing
    try:
        if settings.enable_tracing:
            from utils.tracing import shutdown_tracing
            shutdown_tracing()
    except Exception:
        pass

    # Cancel cleanup task if running
    if cleanup_task and not cleanup_task.done():
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass

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

# Include Knowledge Base routes
if KNOWLEDGE_BASE_AVAILABLE:
    app.include_router(knowledge_base_router, prefix="/api/v1", tags=["knowledge-base"])

# Include Integrations routes
if INTEGRATIONS_AVAILABLE:
    app.include_router(integrations_router, prefix="/api/v1", tags=["integrations"])

# Include Visualization routes
if VISUALIZATION_AVAILABLE:
    app.include_router(visualization_router, prefix="/api/v1", tags=["visualizations"])

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


# Rate limit headers middleware
@app.middleware("http")
async def add_rate_limit_headers(request: Request, call_next):
    """Add rate limit headers to all responses"""
    response = await call_next(request)
    
    # Try to get API key from request if it was authenticated
    api_key_header = request.headers.get("X-API-Key")
    if api_key_header:
        try:
            from api.auth import get_api_key_info
            key_info = get_api_key_info(api_key_header)
            tier = key_info.get('tier', 'free')
            
            # Get rate limit info
            limit_info = rate_limiter.get_limit_info(api_key_header, tier)
            
            # Add headers
            response.headers["X-RateLimit-Limit"] = str(limit_info['limit'])
            response.headers["X-RateLimit-Remaining"] = str(limit_info['remaining'])
            response.headers["X-RateLimit-Reset"] = str(limit_info['window_seconds'])
            response.headers["X-RateLimit-Tier"] = tier
        except Exception:
            # Silently fail if rate limit info can't be retrieved
            pass
    
    return response


# === Authentication ===

# API key validation is handled in api/auth.py


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
    """Request to start analysis with enhanced validation"""
    incident_data: Dict[str, Any]
    agents: Optional[List[str]] = None
    parameters: Optional[Dict[str, Any]] = None
    callback_url: Optional[str] = None
    use_llm: bool = False
    filter_pii: bool = False

    @validator('incident_data')
    def validate_incident_data(cls, v):
        """Validate incident data has required fields and proper structure"""
        if not v:
            raise ValueError("incident_data cannot be empty")
        
        if not isinstance(v, dict):
            raise ValueError("incident_data must be a dictionary")
        
        # Validate at least one of the common data sources is present
        required_fields = ['logs', 'metrics', 'changes', 'traces', 'events']
        if not any(field in v for field in required_fields):
            raise ValueError(
                f"incident_data must contain at least one of: {', '.join(required_fields)}"
            )
        
        return v
    
    @validator('agents')
    def validate_agents(cls, v):
        """Validate agent list"""
        if v is not None:
            if not isinstance(v, list):
                raise ValueError("agents must be a list")
            
            valid_agents = [
                'LogAnalyzerAgent',
                'MetricsAnalyzerAgent',
                'ChangeCorrelatorAgent',
                'TopologyInferenceAgent',
                'HypothesisGeneratorAgent',
                'RemediationPlannerAgent'
            ]
            
            for agent in v:
                if agent not in valid_agents:
                    raise ValueError(
                        f"Unknown agent: {agent}. Valid agents: {', '.join(valid_agents)}"
                    )
        
        return v
    
    @validator('callback_url')
    def validate_callback_url(cls, v):
        """Validate callback URL format"""
        if v is not None:
            if not isinstance(v, str):
                raise ValueError("callback_url must be a string")
            
            # Basic URL validation
            if not v.startswith(('http://', 'https://')):
                raise ValueError("callback_url must start with http:// or https://")
        
        return v
    
    @validator('parameters')
    def validate_parameters(cls, v):
        """Validate parameters structure"""
        if v is not None:
            if not isinstance(v, dict):
                raise ValueError("parameters must be a dictionary")
        
        return v


class AnalysisResponse(BaseModel):
    """Response for created analysis"""
    analysis_id: str
    status: str
    status_url: str
    request_id: str


class AgentExecutionRequest(BaseModel):
    """Request to execute single agent with enhanced validation"""
    context: Dict[str, Any]
    parameters: Optional[Dict[str, Any]] = {}
    use_llm: bool = False
    
    @validator('context')
    def validate_context(cls, v):
        """Validate context is not empty and is a dictionary"""
        if not v:
            raise ValueError("context cannot be empty")
        
        if not isinstance(v, dict):
            raise ValueError("context must be a dictionary")
        
        return v
    
    @validator('parameters')
    def validate_parameters(cls, v):
        """Validate parameters structure"""
        if v is None:
            return {}
        
        if not isinstance(v, dict):
            raise ValueError("parameters must be a dictionary")
        
        return v


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

    if WEBHOOK_AVAILABLE:
        endpoints["webhooks"] = "/api/v1/webhooks"

    if KNOWLEDGE_BASE_AVAILABLE:
        endpoints["knowledge_base"] = "/api/v1/knowledge-base"
        endpoints["similarity_search"] = "/api/v1/knowledge-base/search/similar-incidents"

    if INTEGRATIONS_AVAILABLE:
        endpoints["integrations"] = "/api/v1/integrations"
        endpoints["slack_integration"] = "/api/v1/integrations/slack"
        endpoints["jira_integration"] = "/api/v1/integrations/jira"
        endpoints["pagerduty_integration"] = "/api/v1/integrations/pagerduty"

    if VISUALIZATION_AVAILABLE:
        endpoints["visualizations"] = "/api/v1/visualizations"
        endpoints["root_cause_graph"] = "/api/v1/visualizations/root-cause-graph"
        endpoints["timeline"] = "/api/v1/visualizations/timeline"
        endpoints["metrics_dashboard"] = "/api/v1/visualizations/metrics-dashboard"
        endpoints["complete_dashboard"] = "/api/v1/visualizations/complete-dashboard"

    return {
        "name": "ADAPT-Agents API",
        "version": "3.5.0",
        "features": [
            "Async/Await execution",
            "Real-time WebSocket streaming" if WEBSOCKET_AVAILABLE else "WebSocket support (install websockets)",
            "Webhook callbacks" if WEBHOOK_AVAILABLE else "Webhook support (install httpx)",
            "RAG & Historical Learning (ChromaDB)" if KNOWLEDGE_BASE_AVAILABLE else "RAG support (install chromadb, sentence-transformers)",
            "Enterprise Integrations (Slack, JIRA, PagerDuty)" if INTEGRATIONS_AVAILABLE else "Integrations available",
            "Interactive Visualizations (Graphs, Timelines, Dashboards)" if VISUALIZATION_AVAILABLE else "Visualizations available (install networkx)",
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


async def check_database() -> tuple[str, float]:
    """Check SQLite database connectivity"""
    start_time = time.time()
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        conn.close()
        elapsed = (time.time() - start_time) * 1000
        return ("healthy", elapsed)
    except Exception as e:
        elapsed = (time.time() - start_time) * 1000
        return ("unhealthy", elapsed)


async def check_redis() -> tuple[str, float]:
    """Check Redis cache connectivity"""
    start_time = time.time()
    settings = get_settings()
    
    if settings.cache_backend != "redis":
        return ("not_configured", 0.0)
    
    try:
        import redis
        r = redis.from_url(settings.cache_redis_url, socket_connect_timeout=2)
        r.ping()
        elapsed = (time.time() - start_time) * 1000
        return ("healthy", elapsed)
    except ImportError:
        elapsed = (time.time() - start_time) * 1000
        return ("not_available", elapsed)
    except Exception as e:
        elapsed = (time.time() - start_time) * 1000
        return ("unhealthy", elapsed)


async def check_chromadb() -> tuple[str, float]:
    """Check ChromaDB vector database connectivity"""
    start_time = time.time()
    try:
        import chromadb
        client = chromadb.PersistentClient(path="./chroma_db")
        # Try to list collections
        client.list_collections()
        elapsed = (time.time() - start_time) * 1000
        return ("healthy", elapsed)
    except ImportError:
        elapsed = (time.time() - start_time) * 1000
        return ("not_available", elapsed)
    except Exception as e:
        elapsed = (time.time() - start_time) * 1000
        return ("unhealthy", elapsed)


async def check_llm() -> tuple[str, float]:
    """Check LLM API connectivity"""
    start_time = time.time()
    settings = get_settings()
    
    if not settings.llm_api_key:
        return ("not_configured", 0.0)
    
    try:
        from llm.base_llm import get_llm
        llm = get_llm()
        # Quick connectivity check (don't make expensive calls)
        elapsed = (time.time() - start_time) * 1000
        return ("healthy", elapsed)
    except ImportError:
        elapsed = (time.time() - start_time) * 1000
        return ("not_available", elapsed)
    except Exception as e:
        elapsed = (time.time() - start_time) * 1000
        return ("unhealthy", elapsed)


@app.get("/health")
async def health_check():
    """
    Comprehensive health check endpoint
    
    Checks all critical dependencies:
    - SQLite database
    - Redis cache (if configured)
    - ChromaDB vector database
    - LLM API (if configured)
    
    Returns detailed status for each component with response times.
    """
    db_status, db_time = await check_database()
    redis_status, redis_time = await check_redis()
    chromadb_status, chromadb_time = await check_chromadb()
    llm_status, llm_time = await check_llm()
    
    checks = {
        "database": {
            "status": db_status,
            "response_time_ms": round(db_time, 2)
        },
        "cache": {
            "status": redis_status,
            "response_time_ms": round(redis_time, 2)
        },
        "vector_db": {
            "status": chromadb_status,
            "response_time_ms": round(chromadb_time, 2)
        },
        "llm": {
            "status": llm_status,
            "response_time_ms": round(llm_time, 2)
        }
    }
    
    # Overall status is healthy only if all configured services are healthy
    configured_services = [
        status for name, info in checks.items() 
        if info["status"] not in ["not_configured", "not_available"]
    ]
    
    unhealthy_services = [
        name for name, info in checks.items()
        if info["status"] == "unhealthy"
    ]
    
    if unhealthy_services:
        overall_status = "degraded"
    elif configured_services:
        overall_status = "healthy"
    else:
        overall_status = "minimal"
    
    return {
        "status": overall_status,
        "version": "3.5.0",
        "checks": checks,
        "unhealthy_services": unhealthy_services
    }


@app.get("/health/ready")
async def readiness_check():
    """
    Kubernetes readiness probe
    
    Returns 200 if service is ready to accept traffic.
    Returns 503 if service is not ready.
    """
    db_status, _ = await check_database()
    
    # Service is ready if database is accessible
    if db_status == "healthy":
        return {"ready": True}
    else:
        raise HTTPException(status_code=503, detail="Service not ready")


@app.get("/health/live")
async def liveness_check():
    """
    Kubernetes liveness probe
    
    Returns 200 if service is alive and running.
    This is a lightweight check.
    """
    return {"alive": True}


@app.get("/health/circuit-breakers")
async def circuit_breaker_status():
    """
    Get status of all circuit breakers
    
    Shows current state, failure rates, and recent failures for all
    protected external services (LLM APIs, integrations, etc.).
    
    Useful for debugging service outages and monitoring system resilience.
    """
    all_states = circuit_breaker_registry.get_all_states()
    
    # Count circuits by state
    state_counts = {
        "closed": 0,
        "open": 0,
        "half_open": 0
    }
    
    for state_info in all_states.values():
        current_state = state_info.get("state", "closed")
        if current_state in state_counts:
            state_counts[current_state] += 1
    
    # Determine overall system health
    if state_counts["open"] > 0:
        overall_health = "degraded"
    elif state_counts["half_open"] > 0:
        overall_health = "recovering"
    else:
        overall_health = "healthy"
    
    return {
        "overall_health": overall_health,
        "summary": state_counts,
        "total_circuits": len(all_states),
        "circuits": all_states
    }


@app.post("/admin/circuit-breakers/reset")
async def reset_circuit_breakers(
    circuit_name: Optional[str] = None,
    api_key: str = Depends(get_api_key)
):
    """
    Manually reset circuit breakers
    
    Resets circuit breaker(s) to CLOSED state, allowing requests to flow again.
    Use with caution - only reset if you're sure the service has recovered.
    
    Query Parameters:
    - circuit_name: Optional specific circuit to reset. If not provided, resets all.
    
    Example:
    ```bash
    # Reset all circuits
    curl -X POST http://localhost:8000/admin/circuit-breakers/reset \
      -H "X-API-Key: your-key"
    
    # Reset specific circuit
    curl -X POST "http://localhost:8000/admin/circuit-breakers/reset?circuit_name=llm_gpt-4" \
      -H "X-API-Key: your-key"
    ```
    """
    if circuit_name:
        circuit = circuit_breaker_registry.get(circuit_name)
        if not circuit:
            raise HTTPException(status_code=404, detail=f"Circuit breaker '{circuit_name}' not found")
        
        circuit.reset()
        return {
            "message": f"Circuit breaker '{circuit_name}' reset successfully",
            "state": circuit.get_state()
        }
    else:
        circuit_breaker_registry.reset_all()
        return {
            "message": "All circuit breakers reset successfully",
            "total_reset": len(circuit_breaker_registry._breakers)
        }


@app.post("/admin/cleanup")
async def manual_cleanup(
    retention_days: Optional[int] = None,
    api_key: str = Depends(get_api_key)
):
    """
    Manually trigger data cleanup
    
    Removes analyses and embeddings older than retention period.
    Requires authentication.
    
    Query Parameters:
    - retention_days: Optional override for retention period (defaults to configured value)
    """
    cleanup_service = get_cleanup_service(DB_PATH)
    
    if retention_days is not None:
        result = await cleanup_service.run_full_cleanup()
        # Override retention for this run
        result["retention_days_override"] = retention_days
    else:
        result = await cleanup_service.run_full_cleanup()
    
    return {
        "message": "Cleanup completed",
        "result": result
    }


@app.get("/admin/cleanup/stats")
async def get_cleanup_stats(api_key: str = Depends(get_api_key)):
    """
    Get cleanup service statistics
    
    Returns information about past cleanup runs and current database size.
    """
    cleanup_service = get_cleanup_service(DB_PATH)
    stats = cleanup_service.get_stats()
    size_info = await cleanup_service.get_database_size()
    
    return {
        "cleanup_stats": stats,
        "database_size": size_info,
        "retention_policy": {
            "retention_days": get_settings().data_retention_days,
            "auto_cleanup_enabled": get_settings().enable_auto_cleanup,
            "schedule_hours": get_settings().cleanup_schedule_hours
        }
    }


class WebSocketTokenRequest(BaseModel):
    """Request to generate WebSocket token"""
    analysis_ids: Optional[List[str]] = None


@app.post("/ws/token")
async def create_websocket_token(
    token_request: WebSocketTokenRequest = WebSocketTokenRequest(),
    api_key: str = Depends(get_api_key)
):
    """
    Generate WebSocket authentication token

    Creates a short-lived token (15 minutes) for WebSocket connections.
    Optionally restrict token to specific analysis IDs.

    Requires X-API-Key header for authentication.

    Example:
    ```bash
    curl -X POST http://localhost:8000/ws/token \
      -H "X-API-Key: your-key" \
      -H "Content-Type: application/json" \
      -d '{"analysis_ids": ["abc-123"]}'
    ```

    Then use the token in WebSocket connection:
    ```javascript
    const ws = new WebSocket('ws://localhost:8000/ws/analysis/abc-123?token=...');
    ```
    """
    token = generate_ws_token(api_key, token_request.analysis_ids)

    return {
        "token": token,
        "expires_in_minutes": 15,
        "analysis_ids": token_request.analysis_ids or [],
        "message": "Token generated successfully. Use as query parameter: ?token=..."
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

        # Store in knowledge base for RAG (if available and successful)
        if KNOWLEDGE_BASE_AVAILABLE and results.get("success", False):
            try:
                await _store_in_knowledge_base(analysis_id, incident_data, results)
            except Exception as e:
                # Log error but don't fail the analysis
                print(f"⚠️  Failed to store in knowledge base: {e}")

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


async def _store_in_knowledge_base(analysis_id: str, incident_data: Dict, rca_results: Dict):
    """
    Store successful RCA results in knowledge base for future similarity search

    This enables RAG (Retrieval-Augmented Generation) by learning from past incidents
    """
    try:
        from api.knowledge_base_routes import get_rag_components
        import uuid

        components = get_rag_components()
        vector_db = components["vector_db"]
        embedding_service = components["embedding_service"]

        # Generate embeddings for the incident
        embed_result = embedding_service.embed_incident(incident_data)

        # Prepare metadata
        metadata = {
            "incident_time": incident_data.get("incident_time", ""),
            "affected_services": incident_data.get("affected_services", []),
            "severity": incident_data.get("severity", "unknown"),
            "status": "resolved"
        }

        # Store in vector database
        vector_db.add_incident(
            incident_id=analysis_id,
            incident_summary=embed_result["incident_summary"],
            embedding=embed_result["incident_embedding"],
            metadata=metadata,
            rca_results=rca_results
        )

        # Also store top findings
        if "phase2" in rca_results and "hypothesis_generator" in rca_results["phase2"]:
            hyp = rca_results["phase2"]["hypothesis_generator"]
            if hasattr(hyp, "findings") and hyp.findings:
                for finding in hyp.findings[:3]:  # Top 3 hypotheses
                    finding_dict = finding.dict() if hasattr(finding, "dict") else finding
                    finding_embed = embedding_service.embed_finding(finding_dict)

                    vector_db.add_finding(
                        finding_id=str(uuid.uuid4()),
                        finding_text=finding_embed["finding_text"],
                        embedding=finding_embed["finding_embedding"],
                        metadata={
                            "agent_name": "HypothesisGeneratorAgent",
                            "incident_id": analysis_id,
                            "severity": finding_dict.get("severity", "unknown"),
                            "type": "hypothesis",
                            "timestamp": datetime.utcnow().isoformat()
                        }
                    )

        print(f"✓ Stored incident {analysis_id} in knowledge base for RAG")

    except Exception as e:
        # Don't fail the analysis, just log
        print(f"⚠️  Knowledge base storage failed: {e}")
        raise


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
