"""
Root Cause Graph Generator
Creates interactive dependency graphs showing root cause relationships
"""

from typing import Dict, Any, List, Optional
import networkx as nx
import json


class RootCauseGraphGenerator:
    """
    Generates interactive root cause dependency graphs

    Features:
    - Service dependency visualization
    - Hypothesis relationship mapping
    - Causal chain visualization
    - Interactive node exploration
    - Exportable to JSON, DOT, GraphML
    """

    def __init__(self):
        """Initialize graph generator"""
        self.graph = nx.DiGraph()

    def generate_from_rca(self, rca_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate root cause graph from RCA results

        Args:
            rca_results: Complete RCA analysis results

        Returns:
            Dictionary with graph data in multiple formats
        """
        # Reset graph
        self.graph = nx.DiGraph()

        # Add root node (incident)
        self.graph.add_node("INCIDENT", node_type="incident", label="Incident", color="#ff0000")

        # Extract topology information from Phase 1
        if "phase1" in rca_results and "topology_inference" in rca_results["phase1"]:
            self._add_topology_nodes(rca_results["phase1"]["topology_inference"])

        # Extract findings from Phase 1 agents
        self._add_phase1_findings(rca_results.get("phase1", {}))

        # Add hypotheses from Phase 2
        if "phase2" in rca_results and "hypothesis_generator" in rca_results["phase2"]:
            self._add_hypotheses(rca_results["phase2"]["hypothesis_generator"])

        # Add remediation from Phase 3
        if "phase3" in rca_results and "remediation_planner" in rca_results["phase3"]:
            self._add_remediation(rca_results["phase3"]["remediation_planner"])

        # Convert to various formats
        return {
            "nodes": self._get_nodes(),
            "edges": self._get_edges(),
            "cytoscape": self._to_cytoscape(),
            "d3": self._to_d3(),
            "graphml": self._to_graphml(),
            "dot": self._to_dot(),
            "stats": self._get_stats()
        }

    def _add_topology_nodes(self, topology_results: Any):
        """Add service nodes from topology inference"""
        if hasattr(topology_results, "findings") and topology_results.findings:
            for finding in topology_results.findings:
                finding_dict = finding.dict() if hasattr(finding, "dict") else finding

                # Extract services mentioned
                if "services" in finding_dict.get("details", {}):
                    services = finding_dict["details"]["services"]
                    for service in services:
                        node_id = f"service_{service}"
                        self.graph.add_node(
                            node_id,
                            node_type="service",
                            label=service,
                            color="#4285f4"
                        )
                        self.graph.add_edge("INCIDENT", node_id, relationship="affects")

    def _add_phase1_findings(self, phase1_results: Dict[str, Any]):
        """Add findings from Phase 1 agents"""
        agent_colors = {
            "log_analyzer": "#ffa500",
            "metrics_analyzer": "#00ff00",
            "change_correlator": "#ff00ff",
            "topology_inference": "#00ffff"
        }

        for agent_name, agent_result in phase1_results.items():
            if isinstance(agent_result, Exception):
                continue

            findings = getattr(agent_result, "findings", []) if hasattr(agent_result, "findings") else []

            for idx, finding in enumerate(findings[:3], 1):  # Top 3 findings per agent
                finding_dict = finding.dict() if hasattr(finding, "dict") else finding

                node_id = f"{agent_name}_finding_{idx}"
                self.graph.add_node(
                    node_id,
                    node_type="finding",
                    label=finding_dict.get("description", "Finding")[:50],
                    agent=agent_name,
                    severity=finding_dict.get("severity", "unknown"),
                    color=agent_colors.get(agent_name, "#cccccc"),
                    full_description=finding_dict.get("description", "")
                )

                self.graph.add_edge("INCIDENT", node_id, relationship="finding")

    def _add_hypotheses(self, hypothesis_results: Any):
        """Add hypothesis nodes"""
        if hasattr(hypothesis_results, "findings") and hypothesis_results.findings:
            for idx, finding in enumerate(hypothesis_results.findings[:5], 1):
                finding_dict = finding.dict() if hasattr(finding, "dict") else finding

                node_id = f"hypothesis_{idx}"
                self.graph.add_node(
                    node_id,
                    node_type="hypothesis",
                    label=f"Root Cause {idx}",
                    description=finding_dict.get("description", ""),
                    confidence=finding_dict.get("confidence", "unknown"),
                    color="#ff6b6b",
                    size=30 + idx * 5  # Larger nodes for higher priority
                )

                # Connect to incident
                self.graph.add_edge("INCIDENT", node_id, relationship="root_cause")

    def _add_remediation(self, remediation_results: Any):
        """Add remediation action nodes"""
        if hasattr(remediation_results, "findings") and remediation_results.findings:
            for idx, finding in enumerate(remediation_results.findings[:5], 1):
                finding_dict = finding.dict() if hasattr(finding, "dict") else finding

                node_id = f"remediation_{idx}"
                self.graph.add_node(
                    node_id,
                    node_type="remediation",
                    label=f"Action {idx}",
                    description=finding_dict.get("description", ""),
                    priority=finding_dict.get("priority", "unknown"),
                    color="#51cf66"
                )

                # Connect to first hypothesis (simplified)
                if self.graph.has_node("hypothesis_1"):
                    self.graph.add_edge("hypothesis_1", node_id, relationship="remediate")

    def _get_nodes(self) -> List[Dict]:
        """Get nodes as list of dictionaries"""
        nodes = []
        for node_id, attrs in self.graph.nodes(data=True):
            node = {"id": node_id, **attrs}
            nodes.append(node)
        return nodes

    def _get_edges(self) -> List[Dict]:
        """Get edges as list of dictionaries"""
        edges = []
        for source, target, attrs in self.graph.edges(data=True):
            edge = {"source": source, "target": target, **attrs}
            edges.append(edge)
        return edges

    def _to_cytoscape(self) -> Dict[str, List]:
        """Convert to Cytoscape.js format"""
        elements = []

        # Add nodes
        for node_id, attrs in self.graph.nodes(data=True):
            elements.append({
                "data": {
                    "id": node_id,
                    **attrs
                }
            })

        # Add edges
        for source, target, attrs in self.graph.edges(data=True):
            elements.append({
                "data": {
                    "id": f"{source}_{target}",
                    "source": source,
                    "target": target,
                    **attrs
                }
            })

        return {"elements": elements}

    def _to_d3(self) -> Dict[str, List]:
        """Convert to D3.js force-directed graph format"""
        nodes = []
        links = []

        # Create node index mapping
        node_ids = list(self.graph.nodes())
        node_index = {node_id: idx for idx, node_id in enumerate(node_ids)}

        # Add nodes
        for node_id, attrs in self.graph.nodes(data=True):
            nodes.append({
                "id": node_id,
                "index": node_index[node_id],
                **attrs
            })

        # Add links
        for source, target, attrs in self.graph.edges(data=True):
            links.append({
                "source": node_index[source],
                "target": node_index[target],
                **attrs
            })

        return {"nodes": nodes, "links": links}

    def _to_graphml(self) -> str:
        """Convert to GraphML format"""
        try:
            from io import BytesIO
            buffer = BytesIO()
            nx.write_graphml(self.graph, buffer)
            return buffer.getvalue().decode('utf-8')
        except Exception as e:
            return f"<!-- Error generating GraphML: {str(e)} -->"

    def _to_dot(self) -> str:
        """Convert to DOT format (Graphviz)"""
        dot_lines = ["digraph RootCause {"]
        dot_lines.append("  rankdir=LR;")
        dot_lines.append("  node [shape=box, style=filled];")

        # Add nodes
        for node_id, attrs in self.graph.nodes(data=True):
            label = attrs.get("label", node_id)
            color = attrs.get("color", "#cccccc")
            dot_lines.append(f'  "{node_id}" [label="{label}", fillcolor="{color}"];')

        # Add edges
        for source, target, attrs in self.graph.edges(data=True):
            relationship = attrs.get("relationship", "")
            dot_lines.append(f'  "{source}" -> "{target}" [label="{relationship}"];')

        dot_lines.append("}")
        return "\n".join(dot_lines)

    def _get_stats(self) -> Dict[str, Any]:
        """Get graph statistics"""
        return {
            "total_nodes": self.graph.number_of_nodes(),
            "total_edges": self.graph.number_of_edges(),
            "node_types": self._count_node_types(),
            "avg_degree": sum(dict(self.graph.degree()).values()) / max(self.graph.number_of_nodes(), 1),
            "is_connected": nx.is_weakly_connected(self.graph) if self.graph.number_of_nodes() > 0 else False
        }

    def _count_node_types(self) -> Dict[str, int]:
        """Count nodes by type"""
        counts = {}
        for node_id, attrs in self.graph.nodes(data=True):
            node_type = attrs.get("node_type", "unknown")
            counts[node_type] = counts.get(node_type, 0) + 1
        return counts
