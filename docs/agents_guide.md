# ADAPT-Agents Guide

## Agent Overview

ADAPT-Agents provides six specialized diagnostic agents, each designed for a specific aspect of root cause analysis.

## Agent Catalog

### 1. LogAnalyzerAgent

**Purpose**: Analyzes system logs to identify error patterns, anomalies, and temporal correlations.

**Input**:
- Logs (timestamp, level, service, message)
- Incident time (optional)
- Time range

**Output**:
- Error patterns (recurring exceptions)
- Cascading failures
- Temporal spikes
- Anomalous log behaviors

**Use Cases**:
- Identifying new error types after deployments
- Finding cascading failures across services
- Detecting error bursts around incident time

**Example**:
```python
from agents import LogAnalyzerAgent

agent = LogAnalyzerAgent()
result = agent.execute(BaseAgentInput(
    context={
        "logs": [...]
        "incident_time": "2024-01-15T14:23:00Z"
    }
))
```

### 2. MetricsAnalyzerAgent

**Purpose**: Analyzes time-series metrics to detect anomalies, threshold violations, and correlations.

**Input**:
- Metrics (name, timestamps, values, unit)
- Incident time (optional)
- Baseline period (optional)

**Output**:
- Statistical anomalies (z-score based)
- Threshold violations (CPU > 80%, Memory > 90%)
- Metric correlations (throughput vs latency)
- Saturation patterns

**Use Cases**:
- CPU/Memory spike detection
- Performance degradation analysis
- Resource exhaustion identification

**Example**:
```python
from agents import MetricsAnalyzerAgent

agent = MetricsAnalyzerAgent()
result = agent.execute(BaseAgentInput(
    context={
        "metrics": [
            {
                "name": "cpu_usage",
                "values": [45, 67, 89, 98],
                "timestamps": [...]
            }
        ]
    },
    parameters={
        "anomaly_threshold": 3.0  # z-score
    }
))
```

### 3. ChangeCorrelatorAgent

**Purpose**: Correlates change events (deployments, config changes) with incidents.

**Input**:
- Change events (type, timestamp, service, description)
- Incident time
- Affected services

**Output**:
- Correlated changes (high-risk score)
- Concurrent changes pattern
- Change impact assessment

**Use Cases**:
- Deployment-related incident analysis
- Configuration change correlation
- Change risk scoring

**Risk Scoring**:
- Temporal proximity: 0-30 points
- Service relevance: 0-30 points
- Change type: 0-20 points
- Change magnitude: 0-20 points

**Example**:
```python
from agents import ChangeCorrelatorAgent

agent = ChangeCorrelatorAgent()
result = agent.execute(BaseAgentInput(
    context={
        "changes": [
            {
                "type": "deployment",
                "timestamp": "2024-01-15T14:15:00Z",
                "service": "payment-service"
            }
        ],
        "incident_time": "2024-01-15T14:23:00Z",
        "affected_services": ["payment-service"]
    }
))
```

### 4. TopologyInferenceAgent

**Purpose**: Infers service dependencies and topology from runtime data.

**Input**:
- Distributed traces (spans, parent-child relationships)
- Logs (service interaction patterns)
- Metrics (service-to-service latency)

**Output**:
- Service dependency graph
- Critical paths
- Bottlenecks (SPOFs)
- Circular dependencies

**Use Cases**:
- Understanding failure propagation
- Identifying single points of failure
- Mapping service dependencies

**Example**:
```python
from agents import TopologyInferenceAgent

agent = TopologyInferenceAgent()
result = agent.execute(BaseAgentInput(
    context={
        "traces": [
            {
                "trace_id": "trace-001",
                "spans": [
                    {
                        "service": "api-gateway",
                        "parent_id": None
                    },
                    {
                        "service": "payment-service",
                        "parent_id": "span-1"
                    }
                ]
            }
        ]
    }
))

# Access topology
topology = result.metadata["topology"]
print(f"Services: {topology['services']}")
print(f"Dependencies: {topology['dependencies']}")
```

### 5. HypothesisGeneratorAgent

**Purpose**: Synthesizes findings from multiple agents to generate ranked root cause hypotheses.

**Input**:
- Findings from LogAnalyzer, MetricsAnalyzer, ChangeCorrelator, TopologyInference
- Incident description
- Affected services

**Output**:
- Ranked hypotheses (scored 0-100)
- Supporting evidence from multiple sources
- Validation tests for each hypothesis
- Identified failure patterns

**Failure Patterns Recognized**:
- Deployment-induced memory leak
- Resource pool exhaustion
- Cascading timeout
- Database performance degradation

**Hypothesis Scoring**:
- Evidence strength: 0-40 points
- Evidence diversity: 0-20 points
- Temporal correlation: 0-20 points
- Pattern match: 0-20 points

**Example**:
```python
from agents import HypothesisGeneratorAgent

agent = HypothesisGeneratorAgent()
result = agent.execute(BaseAgentInput(
    context={
        "log_findings": log_results.findings,
        "metrics_findings": metrics_results.findings,
        "change_findings": change_results.findings
    },
    parameters={
        "max_hypotheses": 5
    }
))

# Top hypothesis
top = result.findings[0]
print(f"Hypothesis: {top.description}")
print(f"Score: {top.metadata['hypothesis_score']}/100")
print(f"Tests: {top.metadata['validation_tests']}")
```

### 6. RemediationPlannerAgent

**Purpose**: Generates actionable remediation plans based on validated hypotheses.

**Input**:
- Validated hypothesis
- Current system state
- Remediation capabilities (can_rollback, can_scale, etc.)

**Output**:
- Immediate mitigation plan (< 5 min)
- Short-term fix plan (< 1 hour)
- Long-term prevention plan
- Step-by-step procedures with rollback

**Plan Types**:
1. **Immediate**: Rollback, scale, restart, circuit breaker
2. **Short-term**: Code fix, config update, resource adjustment
3. **Long-term**: Monitoring, testing, documentation

**Example**:
```python
from agents import RemediationPlannerAgent

agent = RemediationPlannerAgent()
result = agent.execute(BaseAgentInput(
    context={
        "validated_hypothesis": {
            "description": "Memory leak in v2.4.1",
            "failure_pattern": "deployment_induced_memory_leak"
        },
        "capabilities": {
            "can_rollback": True,
            "can_scale": True,
            "can_restart": True
        }
    }
))

# Get immediate plan
immediate = [p for p in result.findings if p.metadata["plan_type"] == "immediate"][0]
for step in immediate.metadata["steps"]:
    print(f"{step['step_number']}. {step['action']}")
    print(f"   Command: {step['command']}")
```

## Agent Chaining

Agents are designed to work in chains:

```
LogAnalyzer ─┐
MetricsAnalyzer ─┼─→ HypothesisGenerator ─→ RemediationPlanner
ChangeCorrelator ─┤
TopologyInference ─┘
```

Use the `AgentOrchestrator` to run chains automatically:

```python
from chains.orchestrator import AgentOrchestrator

orchestrator = AgentOrchestrator()
results = orchestrator.execute_rca_chain(incident_data)
```

## Best Practices

1. **Use All Agents**: More agents = better hypotheses
2. **Provide Complete Data**: More data points = higher confidence
3. **Check Confidence**: Only act on HIGH confidence findings
4. **Validate Hypotheses**: Use validation tests before remediation
5. **Handle Failures**: Use error_strategy="continue" for resilience
