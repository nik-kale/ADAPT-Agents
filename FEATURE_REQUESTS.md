# ADAPT-Agents Feature Requests

**Repository Analysis Date:** 2025-12-26
**Analyzed Version:** v3.5.0
**Analysis Framework:** Code Quality, Security, Observability, Documentation, Functional Enhancements, Architecture

---

## Summary Table

| # | Feature | Category | Effort | Value | Priority |
|---|---------|----------|--------|-------|----------|
| 1 | Replace Hardcoded API Keys with Environment-Based Auth | Security | Low | High | 3.0 |
| 2 | Add Distributed Rate Limiting with Redis | Architecture | Medium | High | 1.5 |
| 3 | Implement Circuit Breaker for External Services | Architecture | Medium | High | 1.5 |
| 4 | Add WebSocket Authentication | Security | Low | High | 3.0 |
| 5 | Complete OpenTelemetry Distributed Tracing | Observability | Medium | Medium | 1.0 |
| 6 | Add Missing Agent Unit Tests | Code Quality | Medium | Medium | 1.0 |
| 7 | Implement Automatic Data Retention & Cleanup | Functional | Low | Medium | 2.0 |
| 8 | Add Health Check Endpoints for Dependencies | Observability | Low | Medium | 2.0 |
| 9 | Enhance Input Validation with Pydantic Validators | Code Quality | Low | Medium | 2.0 |
| 10 | Add ChromaDB Backup/Export Functionality | Functional | Low | Medium | 2.0 |

---

## Detailed Feature Requests

---

### Feature #1: Replace Hardcoded API Keys with Environment-Based Auth

**Category:** Security
**Effort:** Low | **Value:** High | **Priority Score:** 3.0

#### Problem Statement
The API server (`api/server.py:80-83`) contains hardcoded API keys that pose a significant security risk. Demo keys like `demo-key-12345` are used in production code paths, and multiple route files (`webhook_routes.py`, `knowledge_base_routes.py`, `visualization_routes.py`, `integrations_routes.py`) use a simplified auth pattern `Depends(lambda: "demo-key-12345")` that bypasses real authentication.

#### Proposed Solution
- **Remove hardcoded keys** from `api/server.py` lines 80-83
- **Create environment-based key management** using `config/settings.py`:
  ```python
  api_keys: Dict[str, str] = Field(default_factory=dict)

  @validator('api_keys', pre=True)
  def parse_api_keys(cls, v):
      if isinstance(v, str):
          return json.loads(v)  # ADAPT_API_KEYS='{"key1":"tier1"}'
      return v
  ```
- **Fix all route dependencies** to use the centralized `get_api_key` function from `server.py`
- **Add key rotation support** with optional expiration timestamps
- **Log authentication attempts** (success/failure) for audit trails

#### Affected Files
- `api/server.py:80-83` - Remove hardcoded keys
- `api/webhook_routes.py:34,80,98,123,152,176,205` - Replace lambda dependencies
- `api/knowledge_base_routes.py:86,185,231,263,293,324,353,386` - Replace lambda dependencies
- `api/visualization_routes.py:40,99,167,237` - Replace lambda dependencies
- `api/integrations_routes.py:61,106,148,187,209` - Replace lambda dependencies
- `config/settings.py` - Add API key configuration

#### Success Metrics
- Zero hardcoded credentials in codebase (verifiable via `grep`)
- All API endpoints properly authenticated (integration test coverage)
- Audit logs capture authentication events

---

### Feature #2: Add Distributed Rate Limiting with Redis

**Category:** Architecture
**Effort:** Medium | **Value:** High | **Priority Score:** 1.5

#### Problem Statement
The current rate limiter (`api/server.py:134-166`) uses in-memory storage, which means:
1. Rate limits reset on server restart
2. Rate limits are per-process in multi-worker deployments
3. Horizontal scaling breaks rate limiting entirely

#### Proposed Solution
- **Create `utils/rate_limiter.py`** with pluggable backend support:
  ```python
  class RateLimiterBackend(ABC):
      async def is_allowed(self, key: str, limit: int, window: int) -> bool: ...
      async def get_remaining(self, key: str, limit: int, window: int) -> int: ...

  class RedisRateLimiter(RateLimiterBackend):
      # Use Redis MULTI/EXEC for atomic increment + expire

  class MemoryRateLimiter(RateLimiterBackend):
      # Fallback for development
  ```
- **Implement sliding window algorithm** for smoother rate limiting
- **Add per-tier rate limits** (free: 100/min, premium: 1000/min)
- **Include rate limit headers** in responses (`X-RateLimit-Remaining`, `X-RateLimit-Reset`)
- **Add configuration** in `config/settings.py`

#### Success Metrics
- Rate limits persist across server restarts
- Rate limits synchronized across multiple instances
- Response headers show accurate remaining quota

---

### Feature #3: Implement Circuit Breaker for External Services

**Category:** Architecture
**Effort:** Medium | **Value:** High | **Priority Score:** 1.5

#### Problem Statement
External service calls (LLM APIs, Slack, JIRA, PagerDuty) have no circuit breaker protection. When OpenAI or another service is down, the system will:
1. Continue making failing requests
2. Accumulate timeouts (60s each for LLM)
3. Exhaust connection pools
4. Cascade failures to the entire analysis pipeline

#### Proposed Solution
- **Create `utils/circuit_breaker.py`**:
  ```python
  class CircuitBreaker:
      def __init__(self, failure_threshold: int = 5,
                   recovery_timeout: int = 30,
                   half_open_requests: int = 1):
          self.state = CircuitState.CLOSED
          # ...

      async def execute(self, func, *args, **kwargs):
          if self.state == CircuitState.OPEN:
              raise CircuitOpenError(f"Circuit open, retry after {self.reset_time}")
          # ...
  ```
- **Wrap LLM calls** in `llm/base_llm.py` with circuit breaker
- **Wrap integration calls** in `integrations/*.py` with circuit breaker
- **Add Prometheus metrics** for circuit state transitions
- **Implement fallback strategies**:
  - LLM failure → Use rule-based analysis only
  - Slack failure → Queue for retry
  - JIRA failure → Log and continue

#### Affected Files
- New: `utils/circuit_breaker.py`
- `llm/base_llm.py` - Wrap generate methods
- `llm/openai_llm.py`, `llm/anthropic_llm.py` - Add circuit breaker
- `integrations/slack.py`, `integrations/jira.py`, `integrations/pagerduty.py`

#### Success Metrics
- External service outages don't cascade to core analysis
- Circuit state visible in `/health` endpoint
- Automatic recovery when services return

---

### Feature #4: Add WebSocket Authentication

**Category:** Security
**Effort:** Low | **Value:** High | **Priority Score:** 3.0

#### Problem Statement
WebSocket endpoints in `api/websocket_routes.py` have no authentication. Anyone who can reach the server can:
1. Subscribe to any analysis stream (`/ws/analysis/{analysis_id}`)
2. Receive broadcast messages (`/ws/broadcast`)
3. Monitor agent-specific updates (`/ws/agent/{agent_name}`)

This exposes potentially sensitive incident data.

#### Proposed Solution
- **Add token-based auth for WebSocket connections**:
  ```python
  @router.websocket("/ws/analysis/{analysis_id}")
  async def analysis_websocket(
      websocket: WebSocket,
      analysis_id: str,
      token: str = Query(...)  # Required query param
  ):
      if not await verify_ws_token(token):
          await websocket.close(code=4001, reason="Unauthorized")
          return
      # ...
  ```
- **Generate short-lived WS tokens** via new endpoint `/api/v1/ws/token`
- **Validate analysis_id ownership** - users can only subscribe to their own analyses
- **Add connection logging** for audit purposes

#### Affected Files
- `api/websocket_routes.py` - Add auth to all 3 endpoints
- `api/server.py` - Add `/api/v1/ws/token` endpoint
- `api/websocket_manager.py` - Add connection tracking

#### Success Metrics
- Unauthenticated WS connections rejected with 4001 code
- Token expiration enforced (15 min default)
- Connection audit logs available

---

### Feature #5: Complete OpenTelemetry Distributed Tracing

**Category:** Observability
**Effort:** Medium | **Value:** Medium | **Priority Score:** 1.0

#### Problem Statement
OpenTelemetry dependencies are in `requirements.txt` and mentioned in settings, but actual instrumentation is minimal. The codebase lacks:
1. Trace context propagation through the agent pipeline
2. Span creation for individual agent executions
3. Integration with the included Jaeger instance
4. Correlation between API requests and background analysis jobs

#### Proposed Solution
- **Initialize OpenTelemetry in `api/server.py`** during lifespan startup:
  ```python
  from opentelemetry import trace
  from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
  from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

  if settings.enable_tracing:
      tracer_provider = TracerProvider(resource=Resource.create({
          "service.name": "adapt-agents"
      }))
      tracer_provider.add_span_processor(
          BatchSpanProcessor(OTLPSpanExporter(endpoint=settings.otel_endpoint))
      )
      trace.set_tracer_provider(tracer_provider)
      FastAPIInstrumentor.instrument_app(app)
  ```
- **Add spans in `chains/async_orchestrator.py`** for each phase
- **Propagate trace context** to background tasks
- **Add span attributes** with agent names, finding counts, execution times

#### Affected Files
- `api/server.py` - Initialize OTel provider
- `chains/async_orchestrator.py` - Add phase spans
- `agents/*.py` - Add agent execution spans
- `requirements.txt` - Add `opentelemetry-instrumentation-fastapi`

#### Success Metrics
- Full traces visible in Jaeger UI
- Trace IDs in log output (correlation)
- P95 latency visible per agent

---

### Feature #6: Add Missing Agent Unit Tests

**Category:** Code Quality
**Effort:** Medium | **Value:** Medium | **Priority Score:** 1.0

#### Problem Statement
Only 4 of 6 agents have unit tests:
- ✅ `test_log_analyzer_agent.py`
- ✅ `test_metrics_analyzer_agent.py`
- ✅ `test_change_correlator_agent.py`
- ✅ `test_async_orchestrator.py`
- ❌ `hypothesis_generator_agent.py` - No tests
- ❌ `remediation_planner_agent.py` - No tests
- ❌ `topology_inference_agent.py` - No tests

This creates risk for regressions and makes refactoring dangerous.

#### Proposed Solution
- **Create `tests/unit/test_hypothesis_generator_agent.py`**:
  - Test hypothesis scoring algorithm
  - Test evidence aggregation from multiple agents
  - Test handling of missing agent results
  - Test LLM vs rule-based mode

- **Create `tests/unit/test_remediation_planner_agent.py`**:
  - Test action prioritization
  - Test plan generation for different failure types
  - Test capability constraints (can_rollback, can_scale)

- **Create `tests/unit/test_topology_inference_agent.py`**:
  - Test dependency graph construction
  - Test service discovery from traces
  - Test impact zone calculation

- **Add fixtures** in `tests/conftest.py` for phase2/phase3 inputs

#### Success Metrics
- 100% agent coverage (6/6)
- >80% line coverage per agent
- CI pipeline includes all agent tests

---

### Feature #7: Implement Automatic Data Retention & Cleanup

**Category:** Functional
**Effort:** Low | **Value:** Medium | **Priority Score:** 2.0

#### Problem Statement
The SQLite database (`adapt_agents.db`) and ChromaDB (`./chroma_db`) grow indefinitely. There's no mechanism to:
1. Delete old analyses after a retention period
2. Clean up orphaned ChromaDB embeddings
3. Archive historical data before deletion
4. Manage database size

#### Proposed Solution
- **Add configuration in `config/settings.py`**:
  ```python
  data_retention_days: int = 90
  cleanup_batch_size: int = 100
  enable_auto_cleanup: bool = True
  ```
- **Create `utils/cleanup.py`** with scheduled cleanup:
  ```python
  async def cleanup_old_analyses(retention_days: int):
      cutoff = datetime.utcnow() - timedelta(days=retention_days)
      # Delete from SQLite
      # Delete from ChromaDB
      # Log cleanup stats
  ```
- **Add background scheduler** in server lifespan (using `apscheduler` or simple asyncio task)
- **Create manual cleanup endpoint** `DELETE /api/v1/admin/cleanup`
- **Add cleanup metrics** (records_deleted, space_reclaimed)

#### Success Metrics
- Database size stable over time
- Old data automatically purged per policy
- Cleanup visible in logs/metrics

---

### Feature #8: Add Health Check Endpoints for Dependencies

**Category:** Observability
**Effort:** Low | **Value:** Medium | **Priority Score:** 2.0

#### Problem Statement
The current `/health` endpoint (`api/server.py:496-511`) only checks SQLite connectivity. It doesn't verify:
1. Redis connection (if configured)
2. ChromaDB availability
3. LLM API reachability
4. Integration service status

This makes it difficult to diagnose deployment issues.

#### Proposed Solution
- **Enhance `/health` to include all dependencies**:
  ```python
  @app.get("/health")
  async def health_check():
      checks = {
          "database": await check_sqlite(),
          "cache": await check_redis() if settings.cache_backend == "redis" else "not_configured",
          "vector_db": await check_chromadb(),
          "llm": await check_llm_connection() if settings.llm_api_key else "not_configured"
      }
      overall = "healthy" if all(v == "healthy" for v in checks.values() if v != "not_configured") else "degraded"
      return {"status": overall, "checks": checks, "version": "3.5.0"}
  ```
- **Add `/health/ready`** for Kubernetes readiness probes
- **Add `/health/live`** for Kubernetes liveness probes
- **Include response times** for each dependency check

#### Success Metrics
- K8s probes work correctly
- Degraded status when any dependency fails
- Response times visible per dependency

---

### Feature #9: Enhance Input Validation with Pydantic Validators

**Category:** Code Quality
**Effort:** Low | **Value:** Medium | **Priority Score:** 2.0

#### Problem Statement
Agent input validation is minimal. For example, `LogAnalyzerAgent._analyze_logs_rule_based` assumes `logs` is a list but doesn't validate this. The test file (`test_log_analyzer_agent.py:155-162`) shows that passing `"not a list"` may cause unexpected behavior.

Current issues:
1. No type validation on context fields
2. No range validation on parameters
3. Errors surface deep in processing instead of at input

#### Proposed Solution
- **Enhance `BaseAgentInput` with field validators**:
  ```python
  class LogAnalyzerInput(BaseAgentInput):
      @validator('context')
      def validate_context(cls, v):
          if 'logs' in v and not isinstance(v['logs'], list):
              raise ValueError('logs must be a list')
          if 'logs' in v:
              for log in v['logs']:
                  if not isinstance(log, dict):
                      raise ValueError('each log entry must be a dict')
          return v
  ```
- **Add parameter validation** for thresholds, timeouts, limits
- **Return 422 errors** with clear messages for invalid input
- **Document expected schemas** in OpenAPI

#### Affected Files
- `agents/log_analyzer_agent.py:19-21` - Add validators
- `agents/metrics_analyzer_agent.py` - Add validators
- `agents/change_correlator_agent.py` - Add validators
- `schemas/base_agent.py` - Add base validators

#### Success Metrics
- Invalid input rejected at API boundary
- Clear error messages for validation failures
- OpenAPI schema includes validation rules

---

### Feature #10: Add ChromaDB Backup/Export Functionality

**Category:** Functional
**Effort:** Low | **Value:** Medium | **Priority Score:** 2.0

#### Problem Statement
The RAG knowledge base (`./chroma_db`) contains learned incident patterns that are valuable but:
1. No backup mechanism exists
2. No way to export for migration
3. No restore from backup
4. No disaster recovery plan

#### Proposed Solution
- **Add backup endpoint** `POST /api/v1/knowledge-base/backup`:
  ```python
  @router.post("/backup")
  async def backup_knowledge_base():
      backup_path = f"./backups/chroma_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
      shutil.copytree("./chroma_db", backup_path)
      return {"backup_path": backup_path, "size_mb": get_dir_size(backup_path)}
  ```
- **Add export endpoint** `GET /api/v1/knowledge-base/export` (returns JSON)
- **Add restore endpoint** `POST /api/v1/knowledge-base/restore`
- **Add scheduled backups** via configuration
- **Store backups** in configurable location (local, S3, GCS)

#### Affected Files
- `api/knowledge_base_routes.py` - Add backup/export/restore endpoints
- `rag/vector_db_manager.py` - Add export_all() and import_all() methods
- `config/settings.py` - Add backup configuration

#### Success Metrics
- Backups created on schedule
- Restore tested and documented
- Export format documented for portability

---

## Implementation Priority

### Quick Wins (Do First - High Value, Low Effort)
1. **#1 Replace Hardcoded API Keys** - Critical security fix
2. **#4 Add WebSocket Authentication** - Security gap
3. **#8 Health Check Endpoints** - Operational necessity
4. **#9 Input Validation** - Prevents runtime errors

### Medium Priority (High Impact, Some Effort)
5. **#2 Distributed Rate Limiting** - Required for production scaling
6. **#3 Circuit Breaker** - Resilience improvement
7. **#7 Data Retention** - Operational requirement

### Nice to Have (Improve Quality)
8. **#5 OpenTelemetry Tracing** - Debugging improvement
9. **#6 Missing Tests** - Quality assurance
10. **#10 ChromaDB Backup** - Data protection

---

## Competing Project Comparison

| Feature | ADAPT-Agents | Datadog RCA | PagerDuty AIOps | Grafana ML |
|---------|--------------|-------------|-----------------|------------|
| AI Root Cause Analysis | ✅ | ✅ | ✅ | ❌ |
| Custom Agents | ✅ | ❌ | ❌ | ❌ |
| Self-Hosted | ✅ | ❌ | ❌ | ✅ |
| RAG Learning | ✅ | ❌ | Limited | ❌ |
| Real-time Streaming | ✅ | ✅ | ✅ | ✅ |
| Open Source | ✅ | ❌ | ❌ | ✅ |
| Circuit Breakers | ❌ (proposed) | ✅ | ✅ | ❌ |
| Distributed Tracing | Partial | ✅ | ✅ | ✅ |

**Key Differentiators for ADAPT-Agents:**
- Only fully open-source AI-powered RCA solution
- Customizable agent pipeline
- Self-hosted RAG learning

**Gaps to Address:**
- Production hardening (features #1-4)
- Enterprise observability (feature #5)
- Operational tooling (features #7-8, #10)

---

*Generated by repository analysis on 2025-12-26*
