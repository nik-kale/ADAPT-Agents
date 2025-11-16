# Chain-of-Thought Suppression Pattern

## Overview
Suppresses internal reasoning details while maintaining analytical quality, producing clean, actionable outputs.

## Purpose
- Reduce token usage in production
- Provide concise, actionable findings
- Maintain focus on results, not process
- Enable faster human consumption

## Implementation

### Prompt Modification
```markdown
IMPORTANT: Suppress internal reasoning process. Do NOT include:
- Step-by-step calculations
- Statistical formulas
- Debugging thoughts
- Alternative hypotheses considered

DO include:
- Final conclusions
- Supporting evidence
- Confidence levels
- Actionable recommendations
```

### Example: With vs Without Suppression

**Without Suppression (Verbose):**
```
I will now calculate the z-score for this metric...
Step 1: Calculate mean: (45 + 47 + 46 + ... + 98) / 20 = 52.5
Step 2: Calculate standard deviation...
Step 3: For value 98, z-score = (98 - 52.5) / 12.3 = 3.7
Since 3.7 > 3.0, this is an anomaly.
I considered whether this could be a normal spike...
```

**With Suppression (Concise):**
```
CPU usage anomaly detected: 98% (z-score: 3.7, threshold: 3.0)
Baseline: 52.5% ± 12.3%
Confidence: HIGH
```

## Usage in ADAPT Agents

All agents support suppression via:
```python
input_data = BaseAgentInput(
    context={...},
    parameters={
        "suppress_reasoning": True  # Enable suppression
    }
)
```

## Benefits
- 70-80% reduction in output tokens
- Faster human comprehension
- Easier parsing for downstream automation
- Cost savings at scale

## Trade-offs
- Less explainability for complex analyses
- Harder to debug agent decisions
- May need verbose mode for training/validation

## Best Practices
1. Use suppression in production
2. Keep verbose mode for development
3. Always include confidence levels
4. Provide evidence even when suppressed
5. Document reasoning patterns separately
