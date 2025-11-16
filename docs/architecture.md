# ADAPT-Agents Architecture

## Overview

ADAPT-Agents follows a modular, composable architecture where specialized agents collaborate to perform root cause analysis.

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Agent Orchestrator                       │
│              (Coordination & Error Handling)                 │
└────────────────────┬────────────────────────────────────────┘
                     │
    ┌────────────────┼────────────────┐
    │                │                │
    v                v                v
┌─────────┐    ┌─────────┐    ┌─────────┐
│ Phase 1 │    │ Phase 2 │    │ Phase 3 │
│Analysis │───▶│Synthesis│───▶│Planning │
└─────────┘    └─────────┘    └─────────┘
    │              │              │
    │              │              │
    v              v              v
┌─────────┐    ┌─────────┐    ┌─────────┐
│4 Agents │    │1 Agent  │    │1 Agent  │
│Parallel │    │Sequential    │Sequential
└─────────┘    └─────────┘    └─────────┘
```

## Component Layers

### 1. Schema Layer (`schemas/`)

Defines standard interfaces and data structures:

- **BaseAgent**: Abstract base class for all agents
- **BaseAgentInput**: Standard input schema
- **BaseAgentOutput**: Standard output schema
- **Finding**: Individual diagnostic finding
- **AgentCapabilities**: Agent metadata

**Key Principles**:
- All agents implement same interface
- Structured input/output for composability
- Pydantic validation for type safety

### 2. Agent Layer (`agents/`)

Individual specialized agents:

| Agent | Responsibility | Dependencies |
|-------|---------------|--------------|
| LogAnalyzerAgent | Log analysis | None |
| MetricsAnalyzerAgent | Metrics analysis | None |
| ChangeCorrelatorAgent | Change correlation | None |
| TopologyInferenceAgent | Dependency mapping | None |
| HypothesisGeneratorAgent | Synthesis | All phase 1 agents |
| RemediationPlannerAgent | Action planning | HypothesisGenerator |

**Agent Characteristics**:
- Single responsibility
- Stateless execution
- Independent (Phase 1) or dependent (Phase 2/3)
- Error-resilient

### 3. Orchestration Layer (`chains/`)

Coordinates agent execution:

- **AgentOrchestrator**: Main orchestration class
  - Parallel execution (Phase 1)
  - Sequential execution (Phase 2/3)
  - Error handling and recovery
  - Result aggregation

**Execution Modes**:
1. **Parallel**: Independent agents run simultaneously
2. **Sequential**: Dependent agents run in order
3. **Hybrid**: Combination of both

### 4. Pattern Layer (`patterns/`)

Reusable orchestration patterns:

- **Chain-of-Thought Suppression**: Reduce output verbosity
- **Multi-Agent Delegation**: Divide complex work
- **Hypothesis-Test Loop**: Iterative validation
- **Error Recovery**: Graceful degradation

### 5. Prompt Layer (`prompts/`)

Agent-specific prompt templates:

- Detailed task instructions
- Input/output schemas
- Reasoning constraints
- Example findings
- Guardrails

## Data Flow

### 1. Input Phase

```
Incident Data
    │
    ├─→ logs[]
    ├─→ metrics[]
    ├─→ changes[]
    ├─→ traces[]
    ├─→ incident_time
    └─→ affected_services[]
```

### 2. Phase 1: Parallel Analysis

```
Incident Data
    │
    ├─→ LogAnalyzer ──────────┐
    ├─→ MetricsAnalyzer ───────┤
    ├─→ ChangeCorrelator ──────┼─→ findings[]
    └─→ TopologyInference ─────┘
```

Each agent produces `BaseAgentOutput` with:
- Status (completed/failed)
- Findings[] (structured results)
- Summary (human-readable)
- Confidence level

### 3. Phase 2: Synthesis

```
All Phase 1 findings[]
    │
    └─→ HypothesisGenerator ──→ hypotheses[]
                                 (ranked by score)
```

Hypothesis includes:
- Description
- Evidence (from multiple sources)
- Score (0-100)
- Validation tests

### 4. Phase 3: Planning

```
Top Hypothesis
    │
    └─→ RemediationPlanner ──→ plans[]
                                (immediate/short/long-term)
```

Plans include:
- Step-by-step procedures
- Commands to execute
- Validation criteria
- Rollback procedures

## Error Handling

### Failure Modes

1. **Agent Execution Failure**: Exception during processing
2. **Timeout**: Agent exceeds time limit
3. **Invalid Output**: Malformed result
4. **Dependency Failure**: Upstream agent failed

### Recovery Strategies

1. **Graceful Degradation**: Continue with partial results
2. **Fallback**: Use simpler backup agent
3. **Retry with Backoff**: Retry transient errors
4. **Circuit Breaker**: Prevent cascading failures
5. **Cached Results**: Use previous results when available

### Error Strategy Modes

- `continue`: Proceed with available results (default)
- `fail_fast`: Stop on first failure
- `best_effort`: Try all, report what worked

## Extensibility

### Adding New Agents

1. Extend `BaseAgent`
2. Implement `execute()` method
3. Define input/output using schemas
4. Create prompt template
5. Register in orchestrator

Example:
```python
from schemas import BaseAgent, AgentCapabilities

class CustomAgent(BaseAgent):
    def __init__(self):
        capabilities = AgentCapabilities(
            name="CustomAgent",
            description="Custom analysis",
            input_types=["custom_data"],
            output_types=["custom_findings"]
        )
        super().__init__("CustomAgent", capabilities)

    def execute(self, input_data):
        # Custom logic
        return BaseAgentOutput(...)
```

### Adding New Patterns

1. Create pattern documentation in `patterns/`
2. Implement orchestration logic
3. Add examples
4. Document usage

### Integration Points

- **ADAPT-RCA**: Consume agent findings for RCA workflows
- **ADAPT-UI**: Visualize agent results and hypotheses
- **External LLMs**: Agents can use any LLM backend
- **Observability Platforms**: Ingest data from any source

## Performance Considerations

### Optimization Strategies

1. **Parallel Execution**: Phase 1 agents run simultaneously
2. **Token Optimization**: Suppress reasoning for production
3. **Streaming**: Support for streaming results (future)
4. **Caching**: Cache agent results for reuse
5. **Batching**: Process multiple incidents in batch

### Scalability

- **Stateless Agents**: Horizontal scaling possible
- **Independent Execution**: Agents can run on different nodes
- **Async Support**: Built-in async execution patterns
- **Resource Limits**: Configurable timeouts and token limits

## Security & Privacy

### Best Practices

1. **Input Validation**: All inputs validated via Pydantic
2. **Output Sanitization**: Structured outputs prevent injection
3. **Audit Logging**: Track all agent executions
4. **Data Minimization**: Only process necessary data
5. **Encryption**: Encrypt sensitive data in transit/at rest

### Deployment Models

- **On-Premise**: Run agents in your infrastructure
- **Cloud**: Deploy to cloud with your LLM provider
- **Hybrid**: Mix local and cloud agents
- **Air-Gapped**: Fully offline operation possible
