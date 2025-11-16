# Multi-Agent Role Delegation Pattern

## Overview
Orchestrates multiple specialized agents to solve complex problems through division of labor and expertise.

## Architecture

```
┌─────────────────────┐
│   Orchestrator      │
│  (Coordinator)      │
└──────┬──────────────┘
       │
       ├──────────────┬──────────────┬──────────────┬─────────────┐
       │              │              │              │             │
       v              v              v              v             v
┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
│   Log    │  │ Metrics  │  │  Change  │  │ Topology │  │Hypothesis│
│ Analyzer │  │ Analyzer │  │Correlator│  │Inference │  │Generator │
└──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘
       │              │              │              │             │
       └──────────────┴──────────────┴──────────────┴─────────────┘
                                    │
                                    v
                          ┌──────────────────┐
                          │   Remediation    │
                          │     Planner      │
                          └──────────────────┘
```

## Execution Modes

### 1. Parallel Execution
Run independent agents simultaneously:
```python
# Execute multiple agents in parallel
results = await orchestrator.execute_parallel([
    (log_analyzer, log_data),
    (metrics_analyzer, metrics_data),
    (change_correlator, change_data)
])
```

**Benefits:**
- Faster overall execution
- Independent analysis streams
- Better resource utilization

### 2. Sequential Execution
Run agents in dependency order:
```python
# Execute agents sequentially
log_results = log_analyzer.execute(log_data)
metrics_results = metrics_analyzer.execute(metrics_data)

# Hypothesis generator depends on previous results
hypothesis_results = hypothesis_generator.execute({
    "log_findings": log_results.findings,
    "metrics_findings": metrics_results.findings
})
```

**Benefits:**
- Clear dependencies
- Context accumulation
- Easier debugging

### 3. Hybrid Execution
Combine parallel and sequential:
```python
# Phase 1: Parallel data gathering
phase1_results = await orchestrator.execute_parallel([
    (log_analyzer, log_data),
    (metrics_analyzer, metrics_data),
    (change_correlator, change_data),
    (topology_analyzer, trace_data)
])

# Phase 2: Sequential synthesis
hypothesis = hypothesis_generator.execute(phase1_results)
remediation = remediation_planner.execute(hypothesis)
```

## Responsibility Delegation

### Agent Roles

| Agent | Role | Input | Output |
|-------|------|-------|--------|
| LogAnalyzer | Error detection | Logs | Error patterns |
| MetricsAnalyzer | Anomaly detection | Metrics | Anomalies |
| ChangeCorrelator | Change impact | Changes | Correlations |
| TopologyInference | Dependency mapping | Traces | Topology |
| HypothesisGenerator | Synthesis | All findings | Hypotheses |
| RemediationPlanner | Action planning | Hypothesis | Plans |

### Delegation Rules

1. **Single Responsibility**: Each agent handles one aspect
2. **Clear Interfaces**: Standard input/output schemas
3. **No Overlap**: Avoid duplicate analysis
4. **Composability**: Agents can be mixed/matched
5. **Independence**: Agents don't call each other directly

## Error Handling

### Graceful Degradation
```python
results = []
for agent in agents:
    try:
        result = agent.execute(data)
        results.append(result)
    except Exception as e:
        # Continue with partial results
        results.append(create_error_result(agent, e))

# Proceed with available results
hypothesis_generator.execute({
    "available_findings": [r for r in results if r.status == "completed"]
})
```

### Retry Logic
```python
def execute_with_retry(agent, data, max_retries=2):
    for attempt in range(max_retries + 1):
        try:
            return agent.execute(data)
        except TransientError as e:
            if attempt == max_retries:
                raise
            time.sleep(2 ** attempt)  # Exponential backoff
```

## Communication Patterns

### 1. Direct Pass-Through
```python
# Agent A → Agent B
findings_a = agent_a.execute(data)
result_b = agent_b.execute({"context": {"findings_from_a": findings_a.findings}})
```

### 2. Aggregation
```python
# Agents A, B, C → Agent D
all_findings = []
for agent in [agent_a, agent_b, agent_c]:
    result = agent.execute(data)
    all_findings.extend(result.findings)

synthesized = agent_d.execute({"context": {"all_findings": all_findings}})
```

### 3. Feedback Loop
```python
# Initial hypothesis
hypothesis = hypothesis_generator.execute(initial_data)

# Validation step
validation_data = validation_agent.execute(hypothesis)

# Refined hypothesis
refined_hypothesis = hypothesis_generator.execute({
    "initial_hypothesis": hypothesis,
    "validation_results": validation_data
})
```

## Best Practices

1. **Start Parallel**: Run data-gathering agents in parallel
2. **End Sequential**: Synthesis agents run sequentially
3. **Pass Metadata**: Include execution time, confidence, etc.
4. **Handle Failures**: Don't let one agent failure stop entire chain
5. **Log Everything**: Track agent execution for debugging
6. **Cache Results**: Avoid re-running expensive agents
7. **Set Timeouts**: Prevent hung agents from blocking chain

## Example: Full RCA Chain

```python
async def run_rca_chain(incident_data):
    # Phase 1: Parallel Analysis (4 agents)
    analysis_tasks = [
        log_analyzer.execute(incident_data.logs),
        metrics_analyzer.execute(incident_data.metrics),
        change_correlator.execute(incident_data.changes),
        topology_inference.execute(incident_data.traces)
    ]
    analysis_results = await asyncio.gather(*analysis_tasks)

    # Phase 2: Hypothesis Generation (1 agent)
    hypotheses = hypothesis_generator.execute({
        "log_findings": analysis_results[0].findings,
        "metrics_findings": analysis_results[1].findings,
        "change_findings": analysis_results[2].findings,
        "topology_findings": analysis_results[3].findings
    })

    # Phase 3: Remediation Planning (1 agent)
    plan = remediation_planner.execute({
        "validated_hypothesis": hypotheses.findings[0]
    })

    return {
        "analysis": analysis_results,
        "hypotheses": hypotheses,
        "remediation_plan": plan
    }
```
