# ADAPT-Agents v2.0 Upgrade Guide

Complete guide for upgrading from v1.0 to v2.0.

## 🎯 What's New in v2.0

V2.0 is a major upgrade that transforms ADAPT-Agents from a prototype into a production-ready system:

- ✅ **Full async/await support** for 3-5x performance improvement
- ✅ **LLM integration** with OpenAI, Anthropic, and custom providers
- ✅ **Caching system** (memory/Redis) for cost savings
- ✅ **REST API server** with FastAPI
- ✅ **CLI tool** for command-line operations
- ✅ **Comprehensive testing** with 80%+ coverage
- ✅ **Structured logging** and OpenTelemetry tracing
- ✅ **Prometheus metrics** for observability
- ✅ **Docker & Docker Compose** for easy deployment
- ✅ **Security features** including PII filtering
- ✅ **Configuration management** with environment variables

## 📋 Prerequisites

- Python 3.8+ (3.11 recommended)
- pip or poetry for package management
- (Optional) Redis for caching
- (Optional) Docker for containerized deployment

## 🚀 Step-by-Step Migration

### Step 1: Update Dependencies

```bash
# Backup your current installation
pip freeze > requirements-old.txt

# Install updated package
pip install --upgrade -r requirements.txt

# Or install with specific extras
pip install -e ".[full]"  # Everything
pip install -e ".[api]"   # Just API server
pip install -e ".[llm]"   # Just LLM providers
```

### Step 2: Update Configuration

**Create `.env` file:**

```bash
# Copy example
cp .env.example .env

# Edit with your values
vim .env
```

**Minimum required configuration:**

```env
# LLM Settings (if using LLM integration)
ADAPT_LLM_PROVIDER=openai
ADAPT_LLM_API_KEY=your-api-key-here

# Cache Settings
ADAPT_ENABLE_CACHING=true
ADAPT_CACHE_BACKEND=memory  # or 'redis'

# Logging
ADAPT_LOG_LEVEL=INFO
```

### Step 3: Update Code

#### Agent Execution (Backward Compatible)

```python
# v1.0 code - STILL WORKS!
from agents import LogAnalyzerAgent
from schemas import BaseAgentInput

agent = LogAnalyzerAgent()
result = agent.execute(input_data)

# v2.0 async version (recommended)
import asyncio

async def main():
    agent = LogAnalyzerAgent()
    result = await agent.execute_async(input_data)
    # or with timeout
    result = await agent.execute_with_timeout(input_data, timeout_seconds=30)

asyncio.run(main())
```

#### Orchestrator (Minor Changes)

```python
# v1.0
from chains.orchestrator import AgentOrchestrator

orchestrator = AgentOrchestrator()
results = orchestrator.execute_rca_chain(incident_data)

# v2.0 - Same interface, more options
orchestrator = AgentOrchestrator(error_strategy="continue")  # or "fail_fast"
results = orchestrator.execute_rca_chain(incident_data)

# v2.0 async (coming soon)
# results = await orchestrator.execute_rca_chain_async(incident_data)
```

#### Configuration (New)

```python
# v2.0 - Access configuration
from config.settings import get_settings

settings = get_settings()
print(f"Using LLM: {settings.llm_provider}")
print(f"Cache: {settings.cache_backend}")
```

#### LLM Integration (New)

```python
# v2.0 - Use LLM in custom agents
from llm import OpenAILLM
from config import get_settings

settings = get_settings()
llm = OpenAILLM(
    api_key=settings.llm_api_key,
    model=settings.llm_model
)

# Generate response
response = await llm.generate("Analyze this log...")

# Structured output
result = await llm.generate_structured(
    prompt="Find errors",
    schema={"errors": ["list", "of", "errors"]}
)
```

### Step 4: Update Tests

```python
# Add async tests
import pytest

@pytest.mark.asyncio
async def test_agent_async():
    from agents import LogAnalyzerAgent
    from schemas import BaseAgentInput

    agent = LogAnalyzerAgent()
    input_data = BaseAgentInput(context={"logs": []})

    result = await agent.execute_async(input_data)
    assert result.status == "completed"
```

### Step 5: Deploy

**Local Development:**

```bash
# Run API server
adapt-agents serve

# Or with uvicorn
uvicorn api.server:app --reload
```

**Docker:**

```bash
# Build and run
docker-compose up -d

# Check logs
docker-compose logs -f adapt-agents

# Access API at http://localhost:8000
# Metrics at http://localhost:9090
# Grafana at http://localhost:3000
```

## 🔧 Breaking Changes

### 1. Configuration System

**v1.0:**
```python
# Hardcoded values
MAX_FINDINGS = 10
```

**v2.0:**
```python
from config import get_settings
settings = get_settings()
max_findings = settings.log_analyzer_max_findings
```

### 2. Import Paths

Some utilities moved:

```python
# v1.0
from agents.utils import something

# v2.0
from utils import something
```

### 3. Dependencies

Several new required dependencies:
- `pydantic-settings` (required)
- `fastapi` (optional, for API)
- `click` (optional, for CLI)

Install based on your needs:
```bash
pip install adapt-agents[api,llm,monitoring]
```

## 📦 New Features Usage

### CLI Tool

```bash
# Analyze incident
adapt-agents analyze incident.json

# Generate test data
adapt-agents generate-test-data --scenario memory_leak -o test.json

# Start API server
adapt-agents serve --port 8000

# Start metrics server
adapt-agents metrics --port 9090
```

### REST API

```python
import httpx

# Start analysis
async with httpx.AsyncClient() as client:
    response = await client.post(
        "http://localhost:8000/analyze",
        json={"incident_data": {...}}
    )
    analysis_id = response.json()["analysis_id"]

    # Poll for results
    result = await client.get(f"http://localhost:8000/analyze/{analysis_id}")
```

### Caching

```python
from utils import get_cache

cache = get_cache()

# Cache is automatic, but you can control it
result = await agent.execute_async(input_data)  # Cached automatically

# Clear cache
await cache.clear()
```

### Metrics

```python
from utils.metrics import start_metrics_server

# Start Prometheus endpoint
start_metrics_server(port=9090)

# Metrics automatically recorded for:
# - Agent executions
# - Findings generated
# - Execution duration
# - Cache hits/misses
# - Hypothesis scores
```

### Structured Logging

```python
from utils.logging import get_logger

logger = get_logger(__name__)

logger.info(
    "agent_execution_started",
    agent=agent.name,
    input_size=len(logs),
    incident_id=incident_id
)
```

## 🐛 Troubleshooting

### Issue: Import Errors

**Solution:** Ensure all __init__.py files exist:
```bash
touch utils/__init__.py
touch config/__init__.py
touch llm/__init__.py
```

### Issue: Missing Dependencies

**Solution:** Install extras:
```bash
pip install -e ".[full]"
```

### Issue: LLM API Errors

**Solution:** Check your API key:
```bash
# .env file
ADAPT_LLM_API_KEY=sk-...  # Your actual key
```

### Issue: Cache Connection Errors

**Solution:** Use memory cache for development:
```bash
# .env file
ADAPT_CACHE_BACKEND=memory
```

## ✅ Verification

After migration, verify everything works:

```bash
# Run tests
pytest

# Run example
python examples/example_rca_chain.py

# Check CLI
adapt-agents --version

# Test API (in another terminal)
adapt-agents serve &
curl http://localhost:8000/health
```

## 📚 Additional Resources

- [Full Documentation](docs/getting_started.md)
- [API Reference](docs/api/)
- [Architecture Guide](docs/architecture.md)
- [Examples](examples/)
- [CHANGELOG](CHANGELOG.md)

## 🆘 Getting Help

- GitHub Issues: https://github.com/yourusername/ADAPT-Agents/issues
- Discussions: https://github.com/yourusername/ADAPT-Agents/discussions
- Documentation: https://adapt-agents.readthedocs.io

## 🎉 What's Next?

After successful migration, explore:

1. **LLM Integration** - Connect to OpenAI/Anthropic for intelligent analysis
2. **API Deployment** - Deploy REST API to production
3. **Monitoring** - Set up Grafana dashboards
4. **Custom Agents** - Build domain-specific agents
5. **Integration** - Connect to your observability stack

Welcome to ADAPT-Agents v2.0! 🚀
