# Getting Started with ADAPT-Agents

## Overview

ADAPT-Agents is a modular library of diagnostic LLM agents designed for automated troubleshooting, anomaly analysis, and root cause analysis (RCA) workflows.

## Installation

### Prerequisites
- Python 3.8+
- pip

### Install Dependencies
```bash
pip install pydantic
```

## Quick Start

### 1. Run the Example RCA Chain

```bash
python examples/example_rca_chain.py
```

This will run a complete RCA workflow using synthetic data for a memory leak incident.

### 2. Understanding the Output

The orchestrator runs three phases:

**Phase 1: Diagnostic Analysis** (Parallel)
- LogAnalyzerAgent: Finds error patterns
- MetricsAnalyzerAgent: Detects anomalies
- ChangeCorrelatorAgent: Correlates changes
- TopologyInferenceAgent: Maps dependencies

**Phase 2: Hypothesis Generation** (Sequential)
- HypothesisGeneratorAgent: Synthesizes findings

**Phase 3: Remediation Planning** (Sequential)
- RemediationPlannerAgent: Creates action plans

## Basic Usage

### Running Individual Agents

```python
from agents import LogAnalyzerAgent
from schemas import BaseAgentInput

# Initialize agent
agent = LogAnalyzerAgent()

# Prepare input
input_data = BaseAgentInput(
    context={
        "logs": [
            {
                "timestamp": "2024-01-15T14:23:00Z",
                "level": "ERROR",
                "service": "payment-service",
                "message": "OutOfMemoryError: Java heap space"
            }
        ],
        "incident_time": "2024-01-15T14:23:00Z"
    },
    parameters={}
)

# Execute
result = agent.execute(input_data)

# Print findings
print(f"Status: {result.status}")
print(f"Summary: {result.summary}")
for finding in result.findings:
    print(f"- {finding.description}")
```

### Running Full RCA Chain

```python
from chains.orchestrator import AgentOrchestrator
from examples.synthetic_data import create_memory_leak_incident

# Create orchestrator
orchestrator = AgentOrchestrator()

# Load incident data
incident_data = create_memory_leak_incident()

# Execute chain
results = orchestrator.execute_rca_chain(incident_data)

# Print results
orchestrator.print_results(results)
```

## Incident Data Format

```python
incident_data = {
    "description": "Brief description of the incident",
    "incident_time": "2024-01-15T14:23:00Z",  # ISO 8601
    "affected_services": ["service-name"],

    # Diagnostic data
    "logs": [
        {
            "timestamp": "ISO 8601",
            "level": "ERROR|WARN|INFO",
            "service": "service-name",
            "message": "log message",
            "trace_id": "optional"
        }
    ],

    "metrics": [
        {
            "name": "cpu_usage",
            "service": "service-name",
            "timestamps": ["2024-01-15T14:00:00Z", ...],
            "values": [45, 67, 89, ...],
            "unit": "percentage"
        }
    ],

    "changes": [
        {
            "id": "change-id",
            "type": "deployment|config_change|infrastructure",
            "timestamp": "ISO 8601",
            "service": "service-name",
            "description": "what changed",
            "metadata": {}
        }
    ],

    "traces": [
        {
            "trace_id": "trace-id",
            "spans": [
                {
                    "span_id": "span-id",
                    "service": "service-name",
                    "operation": "operation-name",
                    "parent_id": "parent-span-id",
                    "duration_ms": 100
                }
            ]
        }
    ],

    # Optional
    "current_state": {
        "services_down": [],
        "services_degraded": ["service-name"]
    },

    "capabilities": {
        "can_rollback": True,
        "can_scale": True,
        "can_restart": True
    }
}
```

## Next Steps

- Read [Agent Documentation](agents_guide.md) for details on each agent
- Review [Orchestration Patterns](orchestration_guide.md) for advanced workflows
- See [API Reference](api_reference.md) for complete API details
- Check [Examples](../examples/) for more use cases
