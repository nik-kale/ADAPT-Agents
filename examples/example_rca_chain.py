"""
Example: Complete RCA Chain Execution
Demonstrates full workflow from incident data to remediation plan.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chains.orchestrator import AgentOrchestrator
from examples.synthetic_data import create_memory_leak_incident


def main():
    """Run complete RCA chain example"""
    print("=" * 80)
    print("ADAPT-Agents: Complete RCA Chain Example")
    print("=" * 80)
    print("\nScenario: Memory leak after deployment")
    print("=" * 80 + "\n")

    # Create orchestrator
    orchestrator = AgentOrchestrator(error_strategy="continue")

    # Load synthetic incident data
    incident_data = create_memory_leak_incident()

    print(f"Incident: {incident_data['description']}")
    print(f"Time: {incident_data['incident_time']}")
    print(f"Affected Services: {', '.join(incident_data['affected_services'])}")
    print(f"Data: {len(incident_data['logs'])} logs, {len(incident_data['metrics'])} metrics, "
          f"{len(incident_data['changes'])} changes\n")

    # Execute RCA chain
    print("Executing RCA chain...\n")
    results = orchestrator.execute_rca_chain(incident_data)

    # Print results
    orchestrator.print_results(results)

    # Detailed findings
    print_detailed_findings(results)


def print_detailed_findings(results):
    """Print detailed findings from each agent"""
    print("\n" + "=" * 80)
    print("DETAILED FINDINGS")
    print("=" * 80)

    # Log analysis findings
    if results.get("phase1_analysis", {}).get("log_analysis"):
        log_result = results["phase1_analysis"]["log_analysis"]
        if log_result.findings:
            print("\n[Log Analysis]")
            for finding in log_result.findings:
                print(f"\n  Type: {finding.type}")
                print(f"  Description: {finding.description}")
                print(f"  Severity: {finding.severity}")
                print(f"  Confidence: {finding.confidence}")
                print(f"  Evidence:")
                for evidence in finding.evidence[:3]:
                    print(f"    - {evidence}")

    # Metrics findings
    if results.get("phase1_analysis", {}).get("metrics_analysis"):
        metrics_result = results["phase1_analysis"]["metrics_analysis"]
        if metrics_result.findings:
            print("\n[Metrics Analysis]")
            for finding in metrics_result.findings:
                print(f"\n  Type: {finding.type}")
                print(f"  Description: {finding.description}")
                print(f"  Severity: {finding.severity}")

    # Hypotheses
    if results.get("phase2_hypothesis"):
        hyp_result = results["phase2_hypothesis"]
        if hyp_result.findings:
            print("\n[Root Cause Hypotheses]")
            for i, hypothesis in enumerate(hyp_result.findings, 1):
                print(f"\n  Hypothesis #{i}:")
                print(f"  {hypothesis.description}")
                print(f"  Score: {hypothesis.metadata.get('hypothesis_score', 'N/A')}/100")
                print(f"  Confidence: {hypothesis.confidence}")
                print(f"  Pattern: {hypothesis.metadata.get('failure_pattern', 'N/A')}")
                print(f"  Validation Tests:")
                for test in hypothesis.metadata.get('validation_tests', [])[:3]:
                    print(f"    - {test}")

    # Remediation plans
    if results.get("phase3_remediation"):
        rem_result = results["phase3_remediation"]
        if rem_result.findings:
            print("\n[Remediation Plans]")
            for i, plan in enumerate(rem_result.findings, 1):
                print(f"\n  Plan #{i}: {plan.description}")
                print(f"  Type: {plan.metadata.get('plan_type')}")
                print(f"  Est. Time: {plan.metadata.get('estimated_time_minutes')} min")
                print(f"  Risk Level: {plan.metadata.get('risk_level')}")
                steps = plan.metadata.get('steps', [])
                if steps:
                    print(f"  Steps:")
                    for step in steps[:3]:
                        print(f"    {step['step_number']}. {step['action']}")
                        print(f"       Command: {step['command']}")
                        print(f"       Expected: {step['expected_outcome']}")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
