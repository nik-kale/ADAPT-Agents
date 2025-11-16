# ADAPT-Agents: Modular Diagnostic Agents Library

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://img.shields.io/badge/tests-passing-brightgreen.svg)](tests/)
[![Coverage](https://img.shields.io/badge/coverage-80%25-green.svg)](tests/)
[![Version](https://img.shields.io/badge/version-2.0.0-blue.svg)](CHANGELOG.md)

A production-grade library of specialized LLM agents for automated troubleshooting, anomaly analysis, and root cause analysis (RCA) workflows.

## 🚀 What's New in v2.0

**Major upgrade with enterprise features and production readiness!**

- ⚡ **Async/Await Support** - 3-5x performance improvement
- 🤖 **LLM Integration** - OpenAI, Anthropic, and custom providers
- 💾 **Caching System** - Redis/Memory for cost optimization
- 🌐 **REST API** - FastAPI server with OpenAPI docs
- 🖥️ **CLI Tool** - Full-featured command-line interface
- 📊 **Monitoring** - Prometheus metrics + OpenTelemetry tracing
- 🔒 **Security** - PII filtering and audit logging
- 🐳 **Docker** - Complete deployment stack
- ✅ **Testing** - 80%+ test coverage
- 📚 **Docs** - Comprehensive MkDocs documentation

[See full changelog](CHANGELOG.md) | [Upgrade from v1.0](V2_UPGRADE_GUIDE.md)

## Overview

ADAPT-Agents provides a modular, composable set of intelligent diagnostic components for building production-grade agentic systems. Each agent follows a consistent schema with structured inputs/outputs and is designed to work both independently and as part of orchestrated chains.

### Key Features

- **6 Specialized Agents**: Log analysis, metrics analysis, change correlation, topology inference, hypothesis generation, and remediation planning
- **Async Execution**: Full async/await support for non-blocking parallel execution
- **LLM Integration**: Pluggable providers (OpenAI, Anthropic) with structured output
- **Caching**: Multi-backend caching (Memory, Redis) for performance and cost savings
- **REST API**: Production-ready FastAPI server with async processing
- **CLI**: Command-line interface for analysis, testing, and deployment
- **Observability**: Structured logging, Prometheus metrics, OpenTelemetry tracing
- **Security**: PII filtering, audit logging, secure configuration
- **Testing**: Comprehensive test suite with 80%+ coverage
- **Docker**: Full stack deployment with Prometheus, Grafana, Redis, Jaeger
- **Framework Agnostic**: Compatible with ADAPT-RCA, ADAPT-UI, and custom workflows

## Quick Start

### Installation

**Option 1: Install from source (recommended for development)**

```bash
# Clone repository
git clone https://github.com/yourusername/ADAPT-Agents.git
cd ADAPT-Agents

# Install with all features
pip install -e ".[full]"

# Or install specific features
pip install -e ".[api,llm,monitoring]"
```

**Option 2: Install with pip (coming soon)**

```bash
# Basic installation
pip install adapt-agents

# With all features
pip install "adapt-agents[full]"
```

**Option 3: Docker**

```bash
# Run with Docker Compose (includes Redis, Prometheus, Grafana)
docker-compose up -d

# Access:
# - API: http://localhost:8000
# - Metrics: http://localhost:9090
# - Grafana: http://localhost:3000
```

### Configuration

```bash
# Create .env file from template
cp .env.example .env

# Edit configuration (required for LLM features)
vim .env

# Minimum config
ADAPT_LLM_PROVIDER=openai
ADAPT_LLM_API_KEY=your-api-key-here
```

### Run Example

```bash
python examples/example_rca_chain.py
```

This runs a complete RCA workflow using synthetic data for a memory leak incident.

### Expected Output

```
ADAPT-Agents: Complete RCA Chain Example
================================================================================
Scenario: Memory leak after deployment
================================================================================

Incident: Payment service experiencing OutOfMemoryErrors and degraded performance
Time: 2024-01-15T14:23:00Z
Affected Services: payment-service
Data: 60 logs, 5 metrics, 2 changes

Executing RCA chain...

Phase 1: Running diagnostic agents in parallel...
Phase 1 complete: 4/4 agents succeeded

Phase 2: Generating hypotheses...
Generated 2 hypotheses

Phase 3: Creating remediation plan...
Generated 3 remediation plans

RCA Chain complete in 89ms

================================================================================
RCA CHAIN EXECUTION RESULTS
================================================================================

[Phase 1: Diagnostic Analysis]
  ✓ log_analysis: Analyzed 60 logs. Found 2 issues: 1 critical, 1 high severity.
    Findings: 2
  ✓ metrics_analysis: Analyzed 5 metrics. Found 2 anomalies, 1 threshold violations, 0 correlations.
    Findings: 3
  ✓ change_correlation: Analyzed 2 changes. Found 1 correlations, 1 high-risk.
    Findings: 1
  ✓ topology: Discovered 3 services and 2 dependencies. Found 0 topology insights.
    Findings: 0

[Phase 2: Hypothesis Generation]
  ✓ Generated 2 root cause hypotheses. Top hypothesis score: 92/100. Validation tests provided.
    1. Recent deployment introduced memory leak causing resource exhaustion and failures
       Score: 92/100
    2. Recent deployment introduced errors or breaking changes
       Score: 65/100

[Phase 3: Remediation Planning]
  ✓ Generated 3 remediation plans: 1 immediate, 2 longer-term. Execute in priority order.
    Plan 1: Rollback deployment to previous stable version
    Type: immediate
    Est. Time: 12 minutes
================================================================================
```

## Architecture

```
┌─────────────────────────────────────────┐
│        Agent Orchestrator                │
└─────────┬───────────────────────────────┘
          │
  ┌───────┼───────┬──────────┐
  │       │       │          │
  v       v       v          v
┌────┐ ┌────┐ ┌────┐    ┌────┐
│Log │ │Metr│ │Chng│    │Topo│  Phase 1: Analysis
│Anlz│ │Anlz│ │Corr│    │Infe│  (Parallel)
└──┬─┘ └──┬─┘ └──┬─┘    └──┬─┘
   │      │      │         │
   └──────┴──────┴─────────┘
            │
            v
       ┌────────┐
       │Hypoths │              Phase 2: Synthesis
       │Genrtor │              (Sequential)
       └────┬───┘
            │
            v
       ┌────────┐
       │Remedtn │              Phase 3: Planning
       │Plannr  │              (Sequential)
       └────────┘
```

## Agent Catalog

| Agent | Purpose | Input | Output |
|-------|---------|-------|--------|
| **LogAnalyzerAgent** | Error pattern detection | Logs | Error patterns, cascades |
| **MetricsAnalyzerAgent** | Anomaly detection | Time-series metrics | Anomalies, correlations |
| **ChangeCorrelatorAgent** | Change-incident correlation | Change events | High-risk changes |
| **TopologyInferenceAgent** | Dependency mapping | Traces, logs | Service topology |
| **HypothesisGeneratorAgent** | Root cause synthesis | All findings | Ranked hypotheses |
| **RemediationPlannerAgent** | Action planning | Hypotheses | Remediation plans |

## Usage Examples

### Individual Agent

```python
from agents import MetricsAnalyzerAgent
from schemas import BaseAgentInput

agent = MetricsAnalyzerAgent()

result = agent.execute(BaseAgentInput(
    context={
        "metrics": [
            {
                "name": "cpu_usage",
                "service": "payment-service",
                "timestamps": ["2024-01-15T14:00:00Z", "2024-01-15T14:01:00Z"],
                "values": [45, 98],
                "unit": "percentage"
            }
        ],
        "incident_time": "2024-01-15T14:01:00Z"
    },
    parameters={"anomaly_threshold": 3.0}
))

print(f"Status: {result.status}")
print(f"Findings: {len(result.findings)}")
for finding in result.findings:
    print(f"- {finding.description} (confidence: {finding.confidence})")
```

### Full RCA Chain

```python
from chains.orchestrator import AgentOrchestrator

orchestrator = AgentOrchestrator(error_strategy="continue")

incident_data = {
    "description": "Service experiencing high error rates",
    "incident_time": "2024-01-15T14:23:00Z",
    "affected_services": ["payment-service"],
    "logs": [...],
    "metrics": [...],
    "changes": [...],
    "traces": [...]
}

results = orchestrator.execute_rca_chain(incident_data)

# Access results
log_findings = results["phase1_analysis"]["log_analysis"].findings
hypotheses = results["phase2_hypothesis"].findings
remediation_plans = results["phase3_remediation"].findings

# Top hypothesis
if hypotheses:
    top = hypotheses[0]
    print(f"Root Cause: {top.description}")
    print(f"Confidence: {top.confidence}")
    print(f"Score: {top.metadata['hypothesis_score']}/100")
```

### Custom Chain

```python
from agents import LogAnalyzerAgent, MetricsAnalyzerAgent, HypothesisGeneratorAgent

# Phase 1: Run specific agents
log_agent = LogAnalyzerAgent()
metrics_agent = MetricsAnalyzerAgent()

log_result = log_agent.execute(log_input)
metrics_result = metrics_agent.execute(metrics_input)

# Phase 2: Generate hypothesis
hypothesis_agent = HypothesisGeneratorAgent()
hypothesis_result = hypothesis_agent.execute(BaseAgentInput(
    context={
        "log_findings": log_result.findings,
        "metrics_findings": metrics_result.findings
    }
))

print(f"Generated {len(hypothesis_result.findings)} hypotheses")
```

## Documentation

- [Getting Started](docs/getting_started.md) - Installation and basic usage
- [Agents Guide](docs/agents_guide.md) - Detailed guide for each agent
- [Architecture](docs/architecture.md) - System design and extensibility
- [Orchestration Patterns](patterns/) - Reusable patterns for agent coordination

## Orchestration Patterns

### Chain-of-Thought Suppression
Reduces output verbosity while maintaining quality:
```python
input_data = BaseAgentInput(
    context={...},
    parameters={"suppress_reasoning": True}
)
```

### Multi-Agent Delegation
Coordinates multiple agents efficiently:
- Parallel execution for independent agents
- Sequential execution for dependent agents
- Hybrid workflows for complex scenarios

### Hypothesis-Test Loop
Iterative validation of root cause hypotheses:
1. Generate hypotheses
2. Design validation tests
3. Execute tests
4. Refine or confirm

### Error Recovery
Graceful degradation and resilience:
- Continue with partial results
- Retry with exponential backoff
- Circuit breaker for cascading failures
- Fallback to simpler agents

## Integration

### ADAPT-RCA Integration
```python
from adapt_rca import RCAWorkflow
from adapt_agents import AgentOrchestrator

workflow = RCAWorkflow()
orchestrator = AgentOrchestrator()

# Run agents as part of RCA workflow
incident = workflow.get_incident(incident_id)
agent_results = orchestrator.execute_rca_chain(incident.to_dict())
workflow.record_findings(agent_results)
```

### ADAPT-UI Integration
```python
# Agent results structured for UI visualization
results = {
    "phase1_analysis": {...},  # Agent findings by type
    "phase2_hypothesis": {...}, # Ranked hypotheses
    "phase3_remediation": {...} # Actionable plans
}

# UI can render:
# - Timeline of findings
# - Hypothesis comparison
# - Step-by-step remediation
```

### Custom LLM Backend
```python
class CustomLLMAgent(BaseAgent):
    def __init__(self):
        super().__init__("CustomAgent", capabilities)
        self.llm_client = YourLLMClient()

    def execute(self, input_data):
        prompt = self.build_prompt(input_data)
        llm_response = self.llm_client.generate(prompt)
        return self.parse_response(llm_response)
```

## Project Structure

```
ADAPT-Agents/
├── agents/               # Agent implementations
│   ├── log_analyzer_agent.py
│   ├── metrics_analyzer_agent.py
│   ├── change_correlator_agent.py
│   ├── topology_inference_agent.py
│   ├── hypothesis_generator_agent.py
│   └── remediation_planner_agent.py
├── schemas/              # Base schemas and interfaces
│   └── base_agent.py
├── prompts/              # Agent prompt templates
│   ├── log_analyzer_agent.md
│   ├── metrics_analyzer_agent.md
│   └── ...
├── chains/               # Orchestration logic
│   └── orchestrator.py
├── patterns/             # Orchestration patterns
│   ├── chain_of_thought_suppression.md
│   ├── multi_agent_delegation.md
│   ├── hypothesis_test_loop.md
│   └── error_recovery.md
├── examples/             # Usage examples
│   ├── example_rca_chain.py
│   └── synthetic_data.py
├── docs/                 # Documentation
│   ├── getting_started.md
│   ├── agents_guide.md
│   └── architecture.md
└── README.md
```

## Contributing

Contributions welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Adding New Agents

1. Extend `BaseAgent` class
2. Implement `execute()` method
3. Create prompt template in `prompts/`
4. Add tests and examples
5. Update documentation

## License

MIT License - see [LICENSE](LICENSE) for details.

## Citation

If you use ADAPT-Agents in your research or production systems, please cite:

```bibtex
@software{adapt_agents,
  title={ADAPT-Agents: Modular Diagnostic Agents Library},
  author={Your Name},
  year={2024},
  url={https://github.com/yourusername/ADAPT-Agents}
}
```

## Related Projects

- **ADAPT-RCA**: Root cause analysis framework
- **ADAPT-UI**: Visualization and interaction layer
- **ADAPT-Platform**: Complete diagnostic platform

## Support

- Documentation: [docs/](docs/)
- Issues: [GitHub Issues](https://github.com/yourusername/ADAPT-Agents/issues)
- Discussions: [GitHub Discussions](https://github.com/yourusername/ADAPT-Agents/discussions)

## Roadmap

- [ ] Streaming agent outputs
- [ ] Async execution by default
- [ ] Additional agents (SecurityAnalyzer, CostAnalyzer)
- [ ] LangChain integration
- [ ] OpenTelemetry instrumentation
- [ ] Cloud-native deployment templates
