# ADAPT-Agents: Enterprise-Grade AI-Powered RCA Platform

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://img.shields.io/badge/tests-passing-brightgreen.svg)](tests/)
[![Coverage](https://img.shields.io/badge/coverage-80%25-green.svg)](tests/)
[![Version](https://img.shields.io/badge/version-3.5.0-blue.svg)](CHANGELOG.md)

**Production-ready AI agents for automated incident analysis, root cause detection, and intelligent remediation.**

ADAPT-Agents is an open-source alternative to DataDog, Grafana, and PagerDuty's RCA capabilities, offering real-time streaming, RAG-powered learning, enterprise integrations, and interactive visualizations—all at zero cost.

---

## 🚀 What's New in v3.5

**Enterprise features that rival commercial observability platforms:**

### ✨ **Core Capabilities**
- ⚡ **Async/Await Architecture** - 3-5x faster parallel execution
- 🧠 **RAG & Historical Learning** - Learn from every incident with ChromaDB + sentence-transformers
- 🔄 **Real-Time Streaming** - WebSocket-based live updates during analysis
- 🔗 **Enterprise Integrations** - Native Slack, JIRA, PagerDuty connectors
- 📊 **Interactive Visualizations** - Root cause graphs, timelines, metrics dashboards
- 🎯 **Intelligent Agents** - 6 specialized AI agents with LLM integration

### 🏢 **Enterprise Features**
- 📡 **Webhook Management** - Event-driven callbacks with delivery tracking
- 🗄️ **Vector Database** - Semantic search for similar historical incidents
- 🔐 **API Authentication** - API key auth + rate limiting + request tracking
- 💾 **Persistent Storage** - SQLite backend for analyses, webhooks, integrations
- 🎨 **Multi-Format Export** - Cytoscape.js, D3.js, Plotly, Chart.js, GraphML, DOT

### 📈 **Competitive Positioning**

| Feature | DataDog | Grafana | PagerDuty | **ADAPT-Agents** |
|---------|---------|---------|-----------|------------------|
| Real-Time Streaming | ✓ | ✓ | ✓ | ✅ |
| RAG/AI Learning | ❌ | ❌ | ❌ | ✅ |
| Slack/JIRA/PagerDuty | ✓ | ✓ | Native | ✅ |
| Interactive Viz | ✓ | ✓ | ✓ | ✅ |
| **Open Source** | ❌ | ✓ | ❌ | ✅ |
| **Monthly Cost** | $15-31/host | Free | $21-51/user | **$0** |

**Result:** Enterprise-grade RCA platform at zero cost, with unique AI learning capabilities.

---

## 📦 Installation

### Quick Start (Docker)
```bash
# Clone repository
git clone https://github.com/yourusername/ADAPT-Agents.git
cd ADAPT-Agents

# Start complete stack (API + Redis + Prometheus + Grafana)
docker-compose up -d

# Access:
# - API & Docs: http://localhost:8000/docs
# - Metrics: http://localhost:9090
# - Grafana: http://localhost:3000
```

### Python Installation
```bash
# Install all features
pip install -r requirements.txt

# Or install selectively
pip install fastapi uvicorn httpx websockets  # Core API
pip install chromadb sentence-transformers    # RAG features
pip install networkx                           # Visualizations
pip install openai anthropic                   # LLM providers
```

### Configuration
```bash
# Create .env file
cp .env.example .env

# Configure LLM provider (required for AI features)
echo "ADAPT_LLM_PROVIDER=openai" >> .env
echo "ADAPT_LLM_API_KEY=sk-..." >> .env
```

---

## 🎯 Quick Start Examples

### 1️⃣ Run Complete RCA Analysis
```bash
# Analyze incident using CLI
python -m cli.main analyze examples/incident_data.json

# Output: Root cause + remediation plan in seconds
```

### 2️⃣ Start API Server
```bash
# Start FastAPI server
uvicorn api.server:app --reload

# Access interactive docs at http://localhost:8000/docs
```

### 3️⃣ Analyze Incident via API
```bash
# Create analysis (returns immediately with job ID)
curl -X POST http://localhost:8000/analyze \
  -H "X-API-Key: demo-key-12345" \
  -H "Content-Type: application/json" \
  -d @examples/incident_data.json

# Get results
curl http://localhost:8000/analyze/{analysis_id} \
  -H "X-API-Key: demo-key-12345"
```

### 4️⃣ Real-Time Streaming (WebSocket)
```javascript
// Connect to WebSocket for live updates
const ws = new WebSocket('ws://localhost:8000/ws/analysis/{analysis_id}');

ws.onmessage = (event) => {
  const update = JSON.parse(event.data);
  console.log(`[${update.agent_name}] ${update.status}: ${update.message}`);
};
```

### 5️⃣ Enterprise Integrations
```bash
# Configure Slack integration
curl -X POST http://localhost:8000/api/v1/integrations/slack \
  -H "X-API-Key: demo-key-12345" \
  -d '{"webhook_url": "https://hooks.slack.com/services/..."}'

# Send incident alert to Slack
curl -X POST http://localhost:8000/api/v1/integrations/notify/incident \
  -H "X-API-Key: demo-key-12345" \
  -d '{
    "incident_id": "inc-123",
    "incident_data": {...},
    "slack_channel": "#incidents",
    "create_jira": true,
    "trigger_pagerduty": true
  }'
```

### 6️⃣ Interactive Visualizations
```bash
# Generate root cause dependency graph
curl -X POST http://localhost:8000/api/v1/visualizations/root-cause-graph \
  -H "X-API-Key: demo-key-12345" \
  -d '{"rca_results": {...}, "format": "cytoscape"}'

# Generate complete dashboard (all visualizations)
curl -X POST http://localhost:8000/api/v1/visualizations/complete-dashboard \
  -H "X-API-Key: demo-key-12345" \
  -d '{"incident_data": {...}, "rca_results": {...}}'
```

### 7️⃣ RAG-Powered Similarity Search
```bash
# Store incident in knowledge base (automatic after each analysis)
# Search for similar past incidents
curl -X POST http://localhost:8000/api/v1/knowledge-base/search/similar-incidents \
  -H "X-API-Key: demo-key-12345" \
  -d '{
    "incident_data": {...},
    "n_results": 5,
    "similarity_threshold": 0.7
  }'

# Get insights about recurring patterns
curl http://localhost:8000/api/v1/knowledge-base/incidents/{id}/insights \
  -H "X-API-Key: demo-key-12345"
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     ADAPT-Agents v3.5 Platform                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │  WebSockets  │  │   Webhooks   │  │  REST API    │         │
│  │  (Real-Time) │  │  (Callbacks) │  │  (FastAPI)   │         │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘         │
│         │                 │                  │                  │
│         └─────────────────┴──────────────────┘                  │
│                           │                                     │
│  ┌────────────────────────┴────────────────────────┐           │
│  │         Integration Layer                        │           │
│  │  ┌─────────┐  ┌─────────┐  ┌──────────────┐   │           │
│  │  │  Slack  │  │  JIRA   │  │  PagerDuty   │   │           │
│  │  └─────────┘  └─────────┘  └──────────────┘   │           │
│  └──────────────────────────────────────────────────┘           │
│                           │                                     │
│  ┌────────────────────────┴────────────────────────┐           │
│  │      Streaming Agent Orchestrator                │           │
│  │  ┌───────────────────────────────────────────┐  │           │
│  │  │  Phase 1: Parallel Diagnostic Agents      │  │           │
│  │  │  [Log] [Metrics] [Changes] [Topology]     │  │           │
│  │  └───────────────┬───────────────────────────┘  │           │
│  │                  │                               │           │
│  │  ┌───────────────┴───────────────────────────┐  │           │
│  │  │  Phase 2: Hypothesis Generation (RAG)     │  │           │
│  │  │  [Similar Incidents] → [LLM] → [Hypoths]  │  │           │
│  │  └───────────────┬───────────────────────────┘  │           │
│  │                  │                               │           │
│  │  ┌───────────────┴───────────────────────────┐  │           │
│  │  │  Phase 3: Remediation Planning (RAG)      │  │           │
│  │  │  [Past Solutions] → [LLM] → [Actions]     │  │           │
│  │  └───────────────────────────────────────────┘  │           │
│  └──────────────────────────────────────────────────┘           │
│                           │                                     │
│  ┌────────────────────────┴────────────────────────┐           │
│  │         Intelligence Layer                       │           │
│  │  ┌──────────────┐  ┌──────────────────────┐    │           │
│  │  │  ChromaDB    │  │  sentence-transformers │    │           │
│  │  │  (Vectors)   │  │  (Embeddings)          │    │           │
│  │  └──────────────┘  └──────────────────────┘    │           │
│  └──────────────────────────────────────────────────┘           │
│                           │                                     │
│  ┌────────────────────────┴────────────────────────┐           │
│  │         Visualization Layer                      │           │
│  │  [Graphs] [Timelines] [Dashboards] [Metrics]   │           │
│  │  → Cytoscape, D3.js, Plotly, Chart.js          │           │
│  └──────────────────────────────────────────────────┘           │
│                           │                                     │
│  ┌────────────────────────┴────────────────────────┐           │
│  │         Persistence Layer                        │           │
│  │  [SQLite] [Redis Cache] [Vector DB]            │           │
│  └──────────────────────────────────────────────────┘           │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🤖 AI Agent Catalog

| Agent | Purpose | LLM-Powered | Capabilities |
|-------|---------|-------------|--------------|
| **LogAnalyzerAgent** | Error pattern detection | ✓ | Pattern matching, cascade detection, severity scoring |
| **MetricsAnalyzerAgent** | Anomaly detection | ✓ | Statistical analysis, threshold violations, correlations |
| **ChangeCorrelatorAgent** | Change-incident correlation | ✓ | Temporal correlation, risk scoring, deployment analysis |
| **TopologyInferenceAgent** | Service dependency mapping | ✓ | Dependency graphs, impact analysis, blast radius |
| **HypothesisGeneratorAgent** | Root cause synthesis | ✓ | Multi-agent fusion, RAG enhancement, confidence scoring |
| **RemediationPlannerAgent** | Action planning | ✓ | Prioritization, time estimation, validation tests |

**All agents support:**
- Async/await execution
- Result caching (Redis/Memory)
- Structured output (Pydantic models)
- RAG enhancement with historical context
- PII filtering for sensitive data
- Prometheus metrics tracking

---

## 📡 API Endpoints

### Core Analysis
- `POST /analyze` - Start RCA analysis (async)
- `GET /analyze/{id}` - Get analysis results
- `GET /agents` - List all available agents
- `POST /agents/{name}/execute` - Run specific agent

### Real-Time Streaming (WebSocket)
- `ws://host/ws/analysis/{id}` - Live updates for specific analysis
- `ws://host/ws/broadcast` - System-wide event stream
- `ws://host/ws/agent/{name}` - Agent-specific updates

### Webhooks
- `POST /api/v1/webhooks` - Create webhook subscription
- `GET /api/v1/webhooks` - List webhooks
- `DELETE /api/v1/webhooks/{id}` - Delete webhook
- `GET /api/v1/webhooks/{id}/deliveries` - Delivery history

### Knowledge Base (RAG)
- `POST /api/v1/knowledge-base/incidents` - Store incident
- `POST /api/v1/knowledge-base/search/similar-incidents` - Find similar incidents
- `GET /api/v1/knowledge-base/incidents/{id}/insights` - Get insights
- `GET /api/v1/knowledge-base/stats` - Database statistics

### Integrations
- `POST /api/v1/integrations/slack` - Configure Slack
- `POST /api/v1/integrations/jira` - Configure JIRA
- `POST /api/v1/integrations/pagerduty` - Configure PagerDuty
- `POST /api/v1/integrations/notify/incident` - Send alerts
- `POST /api/v1/integrations/notify/rca-complete` - Send RCA summary

### Visualizations
- `POST /api/v1/visualizations/root-cause-graph` - Generate dependency graph
- `POST /api/v1/visualizations/timeline` - Generate incident timeline
- `POST /api/v1/visualizations/metrics-dashboard` - Generate metrics dashboard
- `POST /api/v1/visualizations/complete-dashboard` - Generate all visualizations

**Full API documentation:** http://localhost:8000/docs

---

## 📊 Feature Showcase

### 1. Real-Time Streaming
```python
# Server-side: Streaming orchestrator automatically sends updates
from chains.streaming_orchestrator import StreamingOrchestrator

orchestrator = StreamingOrchestrator(
    websocket_manager=ws_manager,
    analysis_id=analysis_id
)

# Automatically streams:
# - Agent start/complete events
# - Individual findings as discovered
# - Phase transitions
# - Final results
```

### 2. RAG-Enhanced Analysis
```python
# Automatic: Every successful analysis is stored in ChromaDB
# Future analyses get historical context automatically

# Manual similarity search:
from rag import SimilaritySearchService

similar = similarity_search.find_similar_incidents(
    query_incident=current_incident,
    n_results=5,
    similarity_threshold=0.7
)

# Returns: Top-5 similar past incidents with RCA solutions
```

### 3. Enterprise Integrations
```python
# Configure once, use everywhere
from integrations import IntegrationManager

manager = IntegrationManager()

# Slack
manager.register_slack(integration_id, api_key, webhook_url)

# JIRA
manager.register_jira(integration_id, api_key, jira_url, username, token, project_key)

# PagerDuty
manager.register_pagerduty(integration_id, api_key, pd_api_key, integration_key)

# Notify all configured integrations
await manager.notify_incident(incident_id, incident_data, api_key)
```

### 4. Interactive Visualizations
```python
# Generate root cause dependency graph
from visualization import RootCauseGraphGenerator

graph_gen = RootCauseGraphGenerator()
graph_data = graph_gen.generate_from_rca(rca_results)

# Export in multiple formats:
cytoscape_format = graph_data["cytoscape"]  # For web rendering
d3_format = graph_data["d3"]                # For force-directed graph
graphml_format = graph_data["graphml"]      # For analysis tools
dot_format = graph_data["dot"]              # For Graphviz
```

---

## 📚 Documentation

### Getting Started
- [Installation Guide](docs/installation.md)
- [Configuration](docs/configuration.md)
- [Quick Start Tutorial](docs/quickstart.md)

### Core Features
- [Agent Guide](docs/agents_guide.md) - Detailed guide for each agent
- [Orchestration Patterns](docs/orchestration.md) - Chain composition strategies
- [LLM Integration](docs/llm_integration.md) - Using OpenAI, Anthropic, etc.

### Enterprise Features (v3.2-3.5)
- [Real-Time Streaming](docs/websockets.md) - WebSocket-based live updates
- [Webhook Management](docs/webhooks.md) - Event-driven callbacks
- [RAG & Historical Learning](docs/rag.md) - ChromaDB + semantic search
- [Enterprise Integrations](docs/integrations.md) - Slack, JIRA, PagerDuty
- [Interactive Visualizations](docs/visualizations.md) - Graphs, timelines, dashboards

### API Reference
- [REST API](docs/api_reference.md) - Complete endpoint documentation
- [WebSocket API](docs/websocket_api.md) - Real-time streaming protocols
- [Pydantic Models](docs/schemas.md) - Data structures and validation

### Advanced Topics
- [Architecture](docs/architecture.md) - System design and extensibility
- [Performance Tuning](docs/performance.md) - Optimization strategies
- [Security](docs/security.md) - Authentication, PII filtering, audit logs
- [Deployment](docs/deployment.md) - Docker, Kubernetes, cloud platforms

---

## 🔧 Development

### Project Structure
```
ADAPT-Agents/
├── agents/                    # 6 specialized diagnostic agents
├── chains/                    # Orchestrators (sync, async, streaming)
├── schemas/                   # Pydantic models and base classes
├── llm/                       # LLM provider integrations
├── utils/                     # Caching, logging, metrics, PII filtering
├── api/                       # FastAPI server + routes
│   ├── server.py             # Main FastAPI app (v3.5)
│   ├── websocket_routes.py   # Real-time streaming endpoints
│   ├── webhook_routes.py     # Webhook management
│   ├── knowledge_base_routes.py  # RAG endpoints
│   ├── integrations_routes.py    # Enterprise integrations
│   └── visualization_routes.py   # Interactive visualizations
├── rag/                       # RAG & vector database
│   ├── vector_db_manager.py  # ChromaDB persistence
│   ├── incident_embeddings.py # Sentence-BERT embeddings
│   ├── similarity_search.py  # Semantic search
│   └── rag_enhancer.py       # LLM prompt enhancement
├── integrations/              # Enterprise connectors
│   ├── slack.py              # Slack integration
│   ├── jira.py               # JIRA integration
│   ├── pagerduty.py          # PagerDuty integration
│   └── integration_manager.py # Unified manager
├── visualization/             # Interactive charts & graphs
│   ├── root_cause_graph.py   # Dependency graphs
│   ├── timeline_chart.py     # Incident timelines
│   └── metrics_dashboard.py  # Metrics visualization
├── cli/                       # Command-line interface
├── config/                    # Configuration management
├── examples/                  # Usage examples
├── tests/                     # Test suite (80%+ coverage)
├── docs/                      # Documentation
└── docker/                    # Docker & Kubernetes configs
```

### Running Tests
```bash
# Run all tests
pytest

# With coverage
pytest --cov=. --cov-report=html

# Specific test file
pytest tests/unit/test_async_orchestrator.py

# Integration tests
pytest tests/integration/
```

### Code Quality
```bash
# Format code
black .

# Sort imports
isort .

# Lint
flake8 .

# Type checking
mypy .
```

---

## 🚀 Deployment

### Docker Compose (Recommended)
```bash
# Start complete stack
docker-compose up -d

# Services included:
# - API server (port 8000)
# - Redis cache (port 6379)
# - Prometheus metrics (port 9090)
# - Grafana dashboards (port 3000)
# - ChromaDB vector database (embedded)
```

### Kubernetes
```bash
# Deploy to Kubernetes
kubectl apply -f k8s/

# Includes:
# - API deployment (3 replicas)
# - Redis StatefulSet
# - Prometheus monitoring
# - Ingress configuration
```

### Cloud Platforms
- **AWS**: ECS Fargate + ElastiCache + RDS
- **GCP**: Cloud Run + Memorystore + Cloud SQL
- **Azure**: Container Apps + Redis + PostgreSQL

See [deployment guide](docs/deployment.md) for detailed instructions.

---

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Adding New Features
1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

### Adding New Agents
1. Extend `BaseAgent` or `AsyncBaseAgent`
2. Implement `execute()` or `execute_async()` method
3. Create prompt template in `prompts/`
4. Add tests in `tests/unit/`
5. Update documentation

---

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

---

## 🌟 Star History

If you find ADAPT-Agents useful, please consider starring the repository!

---

## 📞 Support & Community

- **Documentation**: [docs/](docs/)
- **Issues**: [GitHub Issues](https://github.com/yourusername/ADAPT-Agents/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/ADAPT-Agents/discussions)
- **Discord**: [Join our community](https://discord.gg/adapt-agents)

---

## 🏆 Acknowledgments

Built with:
- [FastAPI](https://fastapi.tiangolo.com/) - Modern web framework
- [ChromaDB](https://www.trychroma.com/) - Vector database
- [sentence-transformers](https://www.sbert.net/) - Embeddings
- [NetworkX](https://networkx.org/) - Graph analysis
- [Pydantic](https://pydantic.dev/) - Data validation
- [OpenAI](https://openai.com/) / [Anthropic](https://www.anthropic.com/) - LLM providers

---

## 🎯 What's Next?

**Upcoming in v3.6:**
- 🔮 ML-based anomaly detection with Prophet/ARIMA
- 🧪 Predictive analytics for incident prevention
- 🌐 Multi-tenancy support
- 📱 Mobile-friendly dashboards
- 🔄 Bi-directional integration sync

See [ROADMAP.md](ROADMAP.md) for the complete roadmap.

---

## 📊 Comparison with Commercial Platforms

### DataDog vs ADAPT-Agents
| Feature | DataDog | ADAPT-Agents |
|---------|---------|--------------|
| RCA Analysis | ✓ | ✅ |
| Real-Time Streaming | ✓ | ✅ |
| AI/ML Learning | Limited | ✅ RAG + ChromaDB |
| Integrations | 500+ | Slack/JIRA/PD + extensible |
| Cost | $15-31/host/mo | **FREE** |
| Self-Hosted | ❌ | ✅ |

### Grafana vs ADAPT-Agents
| Feature | Grafana | ADAPT-Agents |
|---------|---------|--------------|
| Dashboards | ✓ | ✅ |
| Alerting | ✓ | ✅ via integrations |
| RCA Automation | Plugins | ✅ Native |
| AI-Powered | ❌ | ✅ |
| Cost | Free | **FREE** |

### PagerDuty vs ADAPT-Agents
| Feature | PagerDuty | ADAPT-Agents |
|---------|-----------|--------------|
| Incident Management | ✓ | ✅ via integrations |
| RCA Automation | AIOps | ✅ Native + RAG |
| Cost | $21-51/user/mo | **FREE** |
| Customizable | Limited | ✅ Full control |

**Winner:** ADAPT-Agents offers enterprise features at zero cost with unique AI learning capabilities.

---

**Built with ❤️ by the open-source community. Join us in revolutionizing incident management!**
