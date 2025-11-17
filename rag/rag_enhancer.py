"""
RAG (Retrieval-Augmented Generation) Enhancer
Enhances LLM prompts with relevant historical context from vector database
"""

from typing import List, Dict, Any, Optional
import json

from rag.similarity_search import SimilaritySearchService
from rag.incident_embeddings import IncidentEmbeddingService


class RAGEnhancer:
    """
    Enhances LLM prompts with RAG (Retrieval-Augmented Generation)

    Workflow:
    1. Takes current incident/query
    2. Finds similar historical incidents
    3. Formats context from past incidents
    4. Injects into LLM prompt for better analysis

    Benefits:
    - LLM learns from past incidents
    - More accurate root cause analysis
    - Better remediation suggestions
    - Pattern recognition across incidents
    """

    def __init__(
        self,
        similarity_search: SimilaritySearchService,
        max_context_incidents: int = 3
    ):
        """
        Initialize RAG enhancer

        Args:
            similarity_search: Similarity search service
            max_context_incidents: Maximum number of past incidents to include in context
        """
        self.similarity_search = similarity_search
        self.max_context_incidents = max_context_incidents

    def enhance_incident_analysis_prompt(
        self,
        current_incident: Dict[str, Any],
        base_prompt: str,
        agent_name: Optional[str] = None
    ) -> str:
        """
        Enhance incident analysis prompt with historical context

        Args:
            current_incident: Current incident being analyzed
            base_prompt: Original prompt for LLM
            agent_name: Name of agent requesting enhancement

        Returns:
            Enhanced prompt with historical context
        """
        # Find similar historical incidents
        similar_incidents = self.similarity_search.find_similar_incidents(
            query_incident=current_incident,
            n_results=self.max_context_incidents,
            similarity_threshold=0.65  # Lower threshold to get more context
        )

        if not similar_incidents:
            # No similar incidents, return base prompt
            return base_prompt

        # Build RAG context section
        context_parts = [
            "\n### Historical Context from Similar Incidents\n",
            f"Found {len(similar_incidents)} similar past incidents for context:\n"
        ]

        for idx, incident in enumerate(similar_incidents, 1):
            similarity_pct = incident["similarity_score"] * 100

            context_parts.append(f"\n**Similar Incident #{idx}** (Similarity: {similarity_pct:.1f}%)")
            context_parts.append(f"- Incident ID: {incident['incident_id']}")
            context_parts.append(f"- Time: {incident['timestamp']}")
            context_parts.append(f"- Summary: {incident['summary']}")

            # Add RCA insights if available
            if incident.get("rca_results"):
                rca = incident["rca_results"]

                # Extract key findings from Phase 2 (Hypothesis)
                if isinstance(rca, dict) and "phase2" in rca:
                    phase2 = rca["phase2"]
                    if "hypothesis_generator" in phase2:
                        hyp = phase2["hypothesis_generator"]
                        if hasattr(hyp, "findings") and hyp.findings:
                            finding = hyp.findings[0]
                            finding_dict = finding.dict() if hasattr(finding, "dict") else finding
                            context_parts.append(f"- Root Cause: {finding_dict.get('description', 'N/A')}")

                # Extract remediation from Phase 3
                if isinstance(rca, dict) and "phase3" in rca:
                    phase3 = rca["phase3"]
                    if "remediation_planner" in phase3:
                        rem = phase3["remediation_planner"]
                        if hasattr(rem, "findings") and rem.findings:
                            finding = rem.findings[0]
                            finding_dict = finding.dict() if hasattr(finding, "dict") else finding
                            context_parts.append(f"- Remediation: {finding_dict.get('description', 'N/A')}")

            context_parts.append("")  # Blank line

        # Add guidance for using context
        context_parts.append("\n**Guidance:**")
        context_parts.append("- Use the above historical incidents to inform your analysis")
        context_parts.append("- Look for similar patterns, root causes, and remediation strategies")
        context_parts.append("- If the current incident closely matches a past one, reference it in your findings")
        context_parts.append("- Learn from what worked (or didn't work) in past remediations\n")

        rag_context = "\n".join(context_parts)

        # Inject context before the base prompt
        enhanced_prompt = f"{rag_context}\n{'-' * 80}\n\n{base_prompt}"

        return enhanced_prompt

    def enhance_hypothesis_generation(
        self,
        current_incident: Dict[str, Any],
        phase1_findings: Dict[str, Any],
        base_prompt: str
    ) -> str:
        """
        Enhance hypothesis generation with relevant past hypotheses

        Args:
            current_incident: Current incident
            phase1_findings: Findings from Phase 1 agents
            base_prompt: Original hypothesis generation prompt

        Returns:
            Enhanced prompt with similar past hypotheses
        """
        # Find similar incidents
        similar_incidents = self.similarity_search.find_similar_incidents(
            query_incident=current_incident,
            n_results=self.max_context_incidents
        )

        if not similar_incidents:
            return base_prompt

        # Extract hypotheses from similar incidents
        context_parts = [
            "\n### Relevant Past Hypotheses\n",
            "Similar incidents had the following root cause hypotheses:\n"
        ]

        for idx, incident in enumerate(similar_incidents, 1):
            if not incident.get("rca_results"):
                continue

            rca = incident["rca_results"]
            if not isinstance(rca, dict) or "phase2" not in rca:
                continue

            phase2 = rca["phase2"]
            if "hypothesis_generator" not in phase2:
                continue

            hyp = phase2["hypothesis_generator"]
            if not hasattr(hyp, "findings") or not hyp.findings:
                continue

            context_parts.append(f"\n**From Similar Incident {incident['incident_id']}:**")

            for finding_idx, finding in enumerate(hyp.findings[:2], 1):  # Top 2 hypotheses
                finding_dict = finding.dict() if hasattr(finding, "dict") else finding
                context_parts.append(f"{finding_idx}. {finding_dict.get('description', '')}")
                if "confidence" in finding_dict:
                    context_parts.append(f"   Confidence: {finding_dict['confidence']}")

        context_parts.append("\n**Use these past hypotheses to:**")
        context_parts.append("- Identify common patterns")
        context_parts.append("- Validate your current hypothesis")
        context_parts.append("- Avoid repeating past mistakes\n")

        rag_context = "\n".join(context_parts)
        enhanced_prompt = f"{rag_context}\n{'-' * 80}\n\n{base_prompt}"

        return enhanced_prompt

    def enhance_remediation_planning(
        self,
        current_incident: Dict[str, Any],
        validated_hypothesis: Dict[str, Any],
        base_prompt: str
    ) -> str:
        """
        Enhance remediation planning with successful past remediations

        Args:
            current_incident: Current incident
            validated_hypothesis: Validated hypothesis from Phase 2
            base_prompt: Original remediation prompt

        Returns:
            Enhanced prompt with past remediation strategies
        """
        # Find similar incidents
        similar_incidents = self.similarity_search.find_similar_incidents(
            query_incident=current_incident,
            n_results=self.max_context_incidents
        )

        if not similar_incidents:
            return base_prompt

        # Extract remediations
        context_parts = [
            "\n### Successful Past Remediations\n",
            "Similar incidents were resolved using these strategies:\n"
        ]

        for idx, incident in enumerate(similar_incidents, 1):
            if not incident.get("rca_results"):
                continue

            rca = incident["rca_results"]
            if not isinstance(rca, dict) or "phase3" not in rca:
                continue

            phase3 = rca["phase3"]
            if "remediation_planner" not in phase3:
                continue

            rem = phase3["remediation_planner"]
            if not hasattr(rem, "findings") or not rem.findings:
                continue

            context_parts.append(f"\n**Remediation from {incident['incident_id']}:**")

            for finding_idx, finding in enumerate(rem.findings[:2], 1):
                finding_dict = finding.dict() if hasattr(finding, "dict") else finding
                context_parts.append(f"{finding_idx}. {finding_dict.get('description', '')}")
                if "priority" in finding_dict:
                    context_parts.append(f"   Priority: {finding_dict['priority']}")
                if "estimated_time" in finding_dict:
                    context_parts.append(f"   Time: {finding_dict['estimated_time']}")

        context_parts.append("\n**Adapt these remediations to:**")
        context_parts.append("- Leverage proven solutions")
        context_parts.append("- Estimate realistic timelines")
        context_parts.append("- Prioritize based on past success\n")

        rag_context = "\n".join(context_parts)
        enhanced_prompt = f"{rag_context}\n{'-' * 80}\n\n{base_prompt}"

        return enhanced_prompt

    def enhance_agent_prompt(
        self,
        agent_name: str,
        current_incident: Dict[str, Any],
        base_prompt: str
    ) -> str:
        """
        Generic agent prompt enhancement

        Routes to specialized enhancement based on agent type

        Args:
            agent_name: Name of agent requesting enhancement
            current_incident: Current incident data
            base_prompt: Base prompt

        Returns:
            Enhanced prompt with RAG context
        """
        if "hypothesis" in agent_name.lower():
            return self.enhance_hypothesis_generation(
                current_incident,
                {},  # Phase1 findings would be passed here
                base_prompt
            )

        elif "remediation" in agent_name.lower():
            return self.enhance_remediation_planning(
                current_incident,
                {},  # Hypothesis would be passed here
                base_prompt
            )

        else:
            # Default incident analysis enhancement
            return self.enhance_incident_analysis_prompt(
                current_incident,
                base_prompt,
                agent_name
            )

    def get_enhancement_stats(self) -> Dict[str, Any]:
        """Get statistics about RAG enhancements"""
        db_stats = self.similarity_search.vector_db.get_collection_stats()

        return {
            "max_context_incidents": self.max_context_incidents,
            "total_incidents_available": db_stats["incidents"]["count"],
            "total_findings_available": db_stats["findings"]["count"],
            "total_remediations_available": db_stats["remediations"]["count"],
            "rag_enabled": True
        }
