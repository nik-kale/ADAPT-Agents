"""
Topology Inference Agent
Infers service dependencies and topology from observational data.
"""

from typing import Dict, Any, List, Set, Tuple
from collections import defaultdict
from schemas import (
    BaseAgent, BaseAgentInput, BaseAgentOutput,
    Finding, AgentStatus, ConfidenceLevel, AgentCapabilities
)


class TopologyInferenceAgent(BaseAgent):
    """
    Specialized agent for inferring service topology:
    - Service discovery from logs/traces/metrics
    - Dependency mapping
    - Critical path identification
    - Bottleneck detection
    """

    def __init__(self):
        capabilities = AgentCapabilities(
            name="TopologyInferenceAgent",
            description="Infers service dependencies and topology from runtime data",
            input_types=["logs", "traces", "metrics"],
            output_types=["findings", "topology", "dependencies"],
            dependencies=[],
            supports_streaming=False
        )
        super().__init__("TopologyInferenceAgent", capabilities)

    def execute(self, input_data: BaseAgentInput) -> BaseAgentOutput:
        """Execute topology inference"""
        start_time = datetime.now()

        try:
            logs = input_data.context.get("logs", [])
            traces = input_data.context.get("traces", [])
            metrics = input_data.context.get("metrics", [])
            parameters = input_data.parameters or {}

            # Build topology
            topology = self._infer_topology(logs, traces, metrics, parameters)

            # Generate findings
            findings = self._analyze_topology(topology)

            # Create summary
            summary = self._generate_summary(topology, findings)
            confidence = self._calculate_confidence(topology)
            next_steps = self._generate_next_steps(findings)

            execution_time = (datetime.now() - start_time).total_seconds() * 1000

            return BaseAgentOutput(
                agent_name=self.name,
                status=AgentStatus.COMPLETED,
                findings=findings,
                summary=summary,
                confidence=confidence,
                next_steps=next_steps,
                errors=[],
                execution_time_ms=execution_time,
                metadata={"topology": topology}
            )

        except Exception as e:
            from datetime import datetime
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            return BaseAgentOutput(
                agent_name=self.name,
                status=AgentStatus.FAILED,
                findings=[],
                summary=f"Analysis failed: {str(e)}",
                confidence=ConfidenceLevel.UNCERTAIN,
                next_steps=["Review input data format", "Ensure trace/log data is available"],
                errors=[str(e)],
                execution_time_ms=execution_time
            )

    def _infer_topology(self, logs: List[Dict], traces: List[Dict],
                       metrics: List[Dict], parameters: Dict) -> Dict:
        """Infer service topology from available data"""
        services = set()
        dependencies = defaultdict(lambda: {"evidence": [], "confidence": 0.0, "call_count": 0})

        # Extract from traces (highest confidence)
        for trace in traces:
            spans = trace.get("spans", [])
            service_names = [span.get("service") for span in spans if span.get("service")]
            services.update(service_names)

            # Build dependencies from parent-child relationships
            span_map = {span.get("span_id"): span for span in spans if span.get("span_id")}

            for span in spans:
                parent_id = span.get("parent_id")
                if parent_id and parent_id in span_map:
                    parent_span = span_map[parent_id]
                    from_svc = parent_span.get("service")
                    to_svc = span.get("service")

                    if from_svc and to_svc and from_svc != to_svc:
                        dep_key = (from_svc, to_svc)
                        dependencies[dep_key]["evidence"].append("trace_span")
                        dependencies[dep_key]["call_count"] += 1

        # Extract from logs (medium confidence)
        for log in logs:
            service = log.get("service")
            if service:
                services.add(service)

            # Simple pattern matching for dependency hints
            message = log.get("message", "").lower()
            if "calling" in message or "request to" in message:
                # Simplified extraction
                dependencies_found = self._extract_deps_from_log(log)
                for from_svc, to_svc in dependencies_found:
                    dep_key = (from_svc, to_svc)
                    dependencies[dep_key]["evidence"].append("log_pattern")

        # Calculate confidence scores
        for dep_key, dep_data in dependencies.items():
            confidence = self._calculate_dependency_confidence(dep_data["evidence"], dep_data["call_count"])
            dependencies[dep_key]["confidence"] = confidence

        # Filter by minimum confidence
        min_confidence = parameters.get("min_confidence", 0.7)
        filtered_deps = {
            k: v for k, v in dependencies.items()
            if v["confidence"] >= min_confidence
        }

        return {
            "services": list(services),
            "dependencies": [
                {
                    "from": from_svc,
                    "to": to_svc,
                    "confidence": data["confidence"],
                    "call_count": data["call_count"],
                    "evidence_types": list(set(data["evidence"]))
                }
                for (from_svc, to_svc), data in filtered_deps.items()
            ]
        }

    def _extract_deps_from_log(self, log: Dict) -> List[Tuple[str, str]]:
        """Extract dependencies from log message (simplified)"""
        # Real implementation would use NLP or regex patterns
        return []

    def _calculate_dependency_confidence(self, evidence: List[str], call_count: int) -> float:
        """Calculate confidence score for a dependency"""
        score = 0.0
        evidence_weights = {
            "trace_span": 1.0,
            "log_pattern": 0.8,
            "metric_correlation": 0.6
        }

        # Sum evidence weights
        for ev_type in set(evidence):
            score += evidence_weights.get(ev_type, 0.3)

        # Boost confidence with call count
        if call_count >= 10:
            score += 0.2
        elif call_count >= 5:
            score += 0.1

        return min(score, 1.0)

    def _analyze_topology(self, topology: Dict) -> List[Finding]:
        """Analyze topology for findings"""
        findings = []

        dependencies = topology.get("dependencies", [])
        services = topology.get("services", [])

        # Find bottlenecks (services with many incoming dependencies)
        incoming_deps = defaultdict(list)
        for dep in dependencies:
            incoming_deps[dep["to"]].append(dep["from"])

        for service, callers in incoming_deps.items():
            if len(callers) >= 5:
                finding = Finding(
                    type="bottleneck",
                    description=f"{service} is a critical dependency for {len(callers)} services (potential SPOF)",
                    confidence=ConfidenceLevel.HIGH,
                    evidence=[
                        f"{len(callers)} services depend on {service}:",
                        *[f"  - {caller} → {service}" for caller in callers[:5]]
                    ],
                    severity="CRITICAL" if len(callers) >= 8 else "HIGH",
                    metadata={
                        "bottleneck_service": service,
                        "dependent_services": callers,
                        "dependency_count": len(callers),
                        "spof_risk": "high" if len(callers) >= 8 else "medium"
                    }
                )
                findings.append(finding)

        # Find high-confidence critical dependencies
        for dep in dependencies:
            if dep["confidence"] >= 0.9 and dep["call_count"] >= 100:
                finding = Finding(
                    type="dependency",
                    description=f"{dep['from']} → {dep['to']} (critical, {dep['call_count']} calls)",
                    confidence=ConfidenceLevel.HIGH,
                    evidence=[
                        f"Confidence: {dep['confidence']:.2f}",
                        f"Call count: {dep['call_count']}",
                        f"Evidence: {', '.join(dep['evidence_types'])}"
                    ],
                    severity="HIGH",
                    metadata={
                        "from_service": dep["from"],
                        "to_service": dep["to"],
                        "dependency_type": "sync",
                        "call_frequency": dep["call_count"],
                        "criticality": "critical",
                        "confidence_score": dep["confidence"]
                    }
                )
                findings.append(finding)

        # Detect circular dependencies (simplified)
        circular_deps = self._detect_circular_dependencies(dependencies)
        for cycle in circular_deps:
            finding = Finding(
                type="circular_dependency",
                description=f"Circular dependency: {' → '.join(cycle + [cycle[0]])}",
                confidence=ConfidenceLevel.MEDIUM,
                evidence=[f"Cycle detected: {' → '.join(cycle + [cycle[0]])}"],
                severity="MEDIUM",
                metadata={"cycle": cycle + [cycle[0]]}
            )
            findings.append(finding)

        return findings[:10]

    def _detect_circular_dependencies(self, dependencies: List[Dict]) -> List[List[str]]:
        """Detect circular dependencies (simplified DFS)"""
        # Build adjacency list
        graph = defaultdict(list)
        for dep in dependencies:
            graph[dep["from"]].append(dep["to"])

        cycles = []
        visited = set()

        def dfs(node, path):
            if node in path:
                # Found cycle
                cycle_start = path.index(node)
                cycle = path[cycle_start:]
                if len(cycle) >= 2 and cycle not in cycles:
                    cycles.append(cycle)
                return

            if node in visited:
                return

            visited.add(node)
            for neighbor in graph[node]:
                dfs(neighbor, path + [node])

        for service in graph:
            dfs(service, [])

        return cycles[:5]  # Return top 5 cycles

    def _generate_summary(self, topology: Dict, findings: List[Finding]) -> str:
        """Generate summary"""
        service_count = len(topology.get("services", []))
        dep_count = len(topology.get("dependencies", []))

        return f"Discovered {service_count} services and {dep_count} dependencies. " \
               f"Found {len(findings)} topology insights."

    def _calculate_confidence(self, topology: Dict) -> ConfidenceLevel:
        """Calculate overall confidence"""
        dependencies = topology.get("dependencies", [])
        if not dependencies:
            return ConfidenceLevel.LOW

        avg_confidence = sum(d["confidence"] for d in dependencies) / len(dependencies)

        if avg_confidence >= 0.85:
            return ConfidenceLevel.HIGH
        elif avg_confidence >= 0.7:
            return ConfidenceLevel.MEDIUM
        return ConfidenceLevel.LOW

    def _generate_next_steps(self, findings: List[Finding]) -> List[str]:
        """Generate next steps"""
        steps = []

        has_bottleneck = any(f.type == "bottleneck" for f in findings)
        has_circular = any(f.type == "circular_dependency" for f in findings)

        if has_bottleneck:
            steps.append("Review bottleneck services for scaling or redundancy options")
        if has_circular:
            steps.append("Refactor circular dependencies to break cycles")

        steps.append("Use topology to trace failure propagation paths")
        steps.append("Validate inferred dependencies against architecture docs")

        return steps


# Import datetime at module level
from datetime import datetime
