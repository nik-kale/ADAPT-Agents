# Hypothesis → Test → Finding Loop Pattern

## Overview
Iterative pattern for generating hypotheses, testing them, and refining findings until root cause is validated.

## Pattern Flow

```
┌─────────────────┐
│  Gather Data    │
└────────┬────────┘
         │
         v
┌─────────────────┐
│ Generate        │◄──────────┐
│ Hypotheses      │           │
└────────┬────────┘           │
         │                    │
         v                    │
┌─────────────────┐           │
│ Select Top      │           │
│ Hypothesis      │           │
└────────┬────────┘           │
         │                    │
         v                    │
┌─────────────────┐           │
│ Design Test     │           │
└────────┬────────┘           │
         │                    │
         v                    │
┌─────────────────┐           │
│ Execute Test    │           │
└────────┬────────┘           │
         │                    │
         v                    │
    ┌────────┐                │
    │Validated?               │
    └────┬────┘               │
         │                    │
    ┌────┴────┐               │
    │         │               │
   Yes       No               │
    │         │               │
    │         └───────────────┘
    │        (Refine/Generate New)
    │
    v
┌─────────────────┐
│  Root Cause     │
│  Identified     │
└─────────────────┘
```

## Phases

### Phase 1: Hypothesis Generation

Generate multiple plausible hypotheses:
```python
hypotheses = [
    {
        "id": 1,
        "description": "Memory leak in v2.4.1",
        "score": 92,
        "tests": ["Check heap dump", "Review code changes"]
    },
    {
        "id": 2,
        "description": "Database connection pool exhaustion",
        "score": 88,
        "tests": ["Check pool size", "Review config changes"]
    },
    {
        "id": 3,
        "description": "External API timeout",
        "score": 65,
        "tests": ["Check API logs", "Test API endpoint"]
    }
]
```

### Phase 2: Hypothesis Selection

Select highest-scoring hypothesis:
```python
def select_hypothesis(hypotheses, validated=None):
    # Filter out already validated/invalidated
    if validated:
        hypotheses = [h for h in hypotheses if h['id'] not in validated]

    # Sort by score
    return sorted(hypotheses, key=lambda h: h['score'], reverse=True)[0]
```

### Phase 3: Test Design

Design tests for hypothesis validation:
```python
tests = {
    "hypothesis_id": 1,
    "description": "Memory leak in v2.4.1",
    "tests": [
        {
            "test_name": "Heap dump analysis",
            "type": "investigation",
            "action": "Analyze heap dump for object retention",
            "expected_positive": "Large number of retained objects",
            "expected_negative": "Normal heap profile"
        },
        {
            "test_name": "Code review",
            "type": "investigation",
            "action": "Review v2.4.1 changes for memory issues",
            "expected_positive": "Code pattern creating leaks",
            "expected_negative": "Clean code, no obvious issues"
        },
        {
            "test_name": "Rollback test",
            "type": "experiment",
            "action": "Rollback to v2.4.0",
            "expected_positive": "Memory returns to baseline",
            "expected_negative": "Memory remains high"
        }
    ]
}
```

### Phase 4: Test Execution

Execute tests and collect results:
```python
def execute_tests(tests):
    results = []
    for test in tests['tests']:
        result = {
            "test_name": test['test_name'],
            "outcome": execute_test_action(test['action']),
            "validates_hypothesis": None
        }

        # Check if outcome matches expected_positive
        if matches(result['outcome'], test['expected_positive']):
            result['validates_hypothesis'] = True
        elif matches(result['outcome'], test['expected_negative']):
            result['validates_hypothesis'] = False
        else:
            result['validates_hypothesis'] = None  # Inconclusive

        results.append(result)

    return results
```

### Phase 5: Validation Decision

Decide if hypothesis is validated:
```python
def is_hypothesis_validated(test_results):
    # Count positive, negative, inconclusive
    positive = sum(1 for r in test_results if r['validates_hypothesis'] is True)
    negative = sum(1 for r in test_results if r['validates_hypothesis'] is False)
    total = len(test_results)

    # Validation criteria
    if positive >= total * 0.7:  # 70%+ tests support
        return "validated"
    elif negative >= total * 0.5:  # 50%+ tests reject
        return "invalidated"
    else:
        return "inconclusive"
```

### Phase 6: Loop Decision

Decide whether to continue loop:
```python
def should_continue_loop(validation_status, hypotheses_remaining):
    if validation_status == "validated":
        return False  # Success! Exit loop

    if not hypotheses_remaining:
        return False  # No more hypotheses to test

    # Continue with next hypothesis
    return True
```

## Complete Loop Implementation

```python
class HypothesisTestLoop:
    def __init__(self, max_iterations=5):
        self.max_iterations = max_iterations
        self.validated = []
        self.invalidated = []

    def run(self, initial_data):
        # Generate initial hypotheses
        hypotheses = self.generate_hypotheses(initial_data)

        for iteration in range(self.max_iterations):
            # Select top hypothesis
            hypothesis = self.select_hypothesis(
                hypotheses,
                exclude=self.validated + self.invalidated
            )

            if not hypothesis:
                break  # No more hypotheses

            # Design tests
            tests = self.design_tests(hypothesis)

            # Execute tests
            test_results = self.execute_tests(tests)

            # Validate
            status = self.is_hypothesis_validated(test_results)

            if status == "validated":
                self.validated.append(hypothesis)
                return {
                    "root_cause": hypothesis,
                    "validation": test_results,
                    "iterations": iteration + 1
                }
            elif status == "invalidated":
                self.invalidated.append(hypothesis)
                # Continue to next hypothesis
            else:
                # Inconclusive - refine hypothesis
                refined = self.refine_hypothesis(hypothesis, test_results)
                hypotheses.append(refined)

        return {
            "root_cause": None,
            "validated": self.validated,
            "invalidated": self.invalidated,
            "iterations": self.max_iterations
        }
```

## Test Types

### 1. Investigation Tests
Examine existing data more deeply:
- Review logs/metrics
- Analyze code/config
- Check documentation

### 2. Correlation Tests
Check if patterns hold:
- Temporal correlation
- Cross-service correlation
- Metric relationships

### 3. Experimental Tests
Actively change system:
- Rollback deployment
- Modify configuration
- Restart services
- Scale resources

## Refinement Strategies

When tests are inconclusive:

### 1. Narrow Scope
```python
# Original: "Memory leak"
# Refined: "Memory leak in User object cache"
```

### 2. Combine Hypotheses
```python
# Hypothesis 1: "Config change"
# Hypothesis 2: "High load"
# Combined: "Config change reduced capacity under high load"
```

### 3. Add Constraints
```python
# Original: "Database slow"
# Refined: "Database slow for specific query type during peak hours"
```

## Exit Conditions

1. **Success**: Hypothesis validated with high confidence
2. **Exhaustion**: All hypotheses tested and invalidated
3. **Timeout**: Maximum iterations reached
4. **Manual Override**: Human intervention required

## Best Practices

1. **Start Broad**: Generate diverse initial hypotheses
2. **Test Cheaply First**: Run low-risk tests before experiments
3. **Fail Fast**: Quickly invalidate unlikely hypotheses
4. **Document Everything**: Record all test results
5. **Set Limits**: Cap iterations to prevent infinite loops
6. **Parallel Tests**: Run independent tests concurrently
7. **Human in Loop**: Allow manual validation for critical decisions

## Example: Full Loop Execution

```python
# Initial incident data
incident = {
    "logs": [...],
    "metrics": [...],
    "changes": [...]
}

# Run loop
loop = HypothesisTestLoop(max_iterations=5)
result = loop.run(incident)

if result['root_cause']:
    print(f"Root cause found: {result['root_cause']}")
    print(f"Validated by {len(result['validation'])} tests")
    print(f"Iterations: {result['iterations']}")
else:
    print("Root cause not conclusively identified")
    print(f"Tested {len(result['invalidated'])} hypotheses")
```
