# Error Recovery Pattern

## Overview
Handles agent failures gracefully, enabling partial results and system resilience.

## Failure Modes

### 1. Agent Execution Failure
Agent throws exception during execution:
```python
try:
    result = agent.execute(data)
except Exception as e:
    result = create_error_result(agent.name, str(e))
```

### 2. Timeout
Agent exceeds execution time limit:
```python
import asyncio

try:
    result = await asyncio.wait_for(
        agent.execute_async(data),
        timeout=30.0
    )
except asyncio.TimeoutError:
    result = create_timeout_result(agent.name)
```

### 3. Invalid Output
Agent returns malformed data:
```python
result = agent.execute(data)
if not validate_output(result):
    result = create_validation_error(agent.name, result)
```

### 4. Dependency Failure
Required upstream agent failed:
```python
if not upstream_result.status == "completed":
    # Skip or use degraded mode
    result = agent.execute_with_partial_data(available_data)
```

## Recovery Strategies

### 1. Graceful Degradation
Continue with partial results:
```python
results = []
for agent in diagnostic_agents:
    try:
        result = agent.execute(data)
        results.append(result)
    except Exception as e:
        logger.error(f"{agent.name} failed: {e}")
        # Continue without this agent's results

# Proceed with whatever succeeded
if results:
    hypothesis_generator.execute({"available_findings": results})
```

### 2. Fallback Agents
Use simpler backup agent:
```python
try:
    result = advanced_agent.execute(data)
except Exception:
    # Fall back to simpler agent
    result = basic_agent.execute(data)
```

### 3. Retry with Backoff
Retry failed operations:
```python
def execute_with_retry(agent, data, max_retries=3):
    for attempt in range(max_retries):
        try:
            return agent.execute(data)
        except TransientError as e:
            if attempt == max_retries - 1:
                raise
            wait_time = 2 ** attempt
            time.sleep(wait_time)
        except PermanentError:
            raise  # Don't retry permanent failures
```

### 4. Circuit Breaker
Prevent cascading failures:
```python
class CircuitBreaker:
    def __init__(self, failure_threshold=5, timeout=60):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half-open

    def call(self, func, *args, **kwargs):
        if self.state == "open":
            if time.time() - self.last_failure_time > self.timeout:
                self.state = "half-open"
            else:
                raise CircuitBreakerOpen("Circuit breaker is open")

        try:
            result = func(*args, **kwargs)
            if self.state == "half-open":
                self.state = "closed"
                self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()

            if self.failure_count >= self.failure_threshold:
                self.state = "open"

            raise
```

### 5. Default/Cached Results
Use previous results when available:
```python
cache = {}

def execute_with_cache(agent, data, cache_key):
    try:
        result = agent.execute(data)
        cache[cache_key] = result
        return result
    except Exception as e:
        if cache_key in cache:
            logger.warning(f"Using cached result for {agent.name}")
            return cache[cache_key]
        raise
```

## Error Reporting

### Structured Error Results
```python
def create_error_result(agent_name, error_message):
    return BaseAgentOutput(
        agent_name=agent_name,
        status=AgentStatus.FAILED,
        findings=[],
        summary=f"Agent execution failed: {error_message}",
        confidence=ConfidenceLevel.UNCERTAIN,
        next_steps=[
            "Review agent configuration",
            "Check input data format",
            "Review agent logs for details"
        ],
        errors=[error_message]
    )
```

### Error Categorization
```python
class AgentError(Exception):
    """Base class for agent errors"""
    pass

class InputValidationError(AgentError):
    """Invalid input data"""
    pass

class ExecutionTimeoutError(AgentError):
    """Agent exceeded time limit"""
    pass

class ResourceExhaustedError(AgentError):
    """Insufficient resources (memory, tokens, etc.)"""
    pass

class DependencyError(AgentError):
    """Required dependency unavailable"""
    pass

class TransientError(AgentError):
    """Temporary error, retry may succeed"""
    pass
```

## Orchestrator Error Handling

```python
class ResilientOrchestrator:
    def __init__(self, agents, error_strategy="continue"):
        self.agents = agents
        self.error_strategy = error_strategy  # "continue", "fail_fast", "best_effort"

    async def execute_chain(self, data):
        results = []
        failed_agents = []

        for agent in self.agents:
            try:
                result = await self._execute_with_timeout(agent, data, timeout=30)
                results.append(result)

                if result.status == AgentStatus.FAILED:
                    failed_agents.append(agent.name)

                    if self.error_strategy == "fail_fast":
                        raise AgentExecutionFailed(f"{agent.name} failed")

            except Exception as e:
                error_result = create_error_result(agent.name, str(e))
                results.append(error_result)
                failed_agents.append(agent.name)

                if self.error_strategy == "fail_fast":
                    raise

        return {
            "results": results,
            "failed_agents": failed_agents,
            "success_rate": len([r for r in results if r.status == "completed"]) / len(results)
        }

    async def _execute_with_timeout(self, agent, data, timeout):
        try:
            return await asyncio.wait_for(
                agent.execute_async(data),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            raise ExecutionTimeoutError(f"{agent.name} exceeded {timeout}s timeout")
```

## Best Practices

1. **Fail Gracefully**: Never crash entire chain for single agent failure
2. **Log Everything**: Detailed error logging for debugging
3. **Retry Transient**: Retry network/temporary errors
4. **Don't Retry Permanent**: Skip retry for validation/config errors
5. **Use Timeouts**: Prevent hung agents
6. **Provide Fallbacks**: Always have backup plan
7. **Monitor Health**: Track agent success rates
8. **Alert on Patterns**: Alert when failure rate exceeds threshold

## Example: Complete Error-Resilient Chain

```python
async def run_resilient_rca(incident_data):
    results = {
        "log_analysis": None,
        "metrics_analysis": None,
        "change_correlation": None,
        "topology": None,
        "hypothesis": None,
        "remediation": None
    }

    # Phase 1: Parallel analysis with individual error handling
    async def safe_execute(agent, data, key):
        try:
            result = await asyncio.wait_for(agent.execute(data), timeout=30)
            results[key] = result
        except Exception as e:
            logger.error(f"{agent.name} failed: {e}")
            results[key] = create_error_result(agent.name, str(e))

    await asyncio.gather(
        safe_execute(log_analyzer, incident_data.logs, "log_analysis"),
        safe_execute(metrics_analyzer, incident_data.metrics, "metrics_analysis"),
        safe_execute(change_correlator, incident_data.changes, "change_correlation"),
        safe_execute(topology_inference, incident_data.traces, "topology"),
        return_exceptions=True
    )

    # Phase 2: Hypothesis generation (requires at least one successful analysis)
    successful_findings = [
        r.findings for r in results.values()
        if r and r.status == AgentStatus.COMPLETED
    ]

    if successful_findings:
        try:
            results["hypothesis"] = await hypothesis_generator.execute({
                "available_findings": successful_findings
            })
        except Exception as e:
            results["hypothesis"] = create_error_result("HypothesisGenerator", str(e))
    else:
        results["hypothesis"] = create_error_result(
            "HypothesisGenerator",
            "No successful diagnostic data available"
        )

    # Phase 3: Remediation (only if hypothesis succeeded)
    if results["hypothesis"] and results["hypothesis"].status == AgentStatus.COMPLETED:
        try:
            results["remediation"] = await remediation_planner.execute({
                "validated_hypothesis": results["hypothesis"].findings[0]
            })
        except Exception as e:
            results["remediation"] = create_error_result("RemediationPlanner", str(e))

    return results
```
