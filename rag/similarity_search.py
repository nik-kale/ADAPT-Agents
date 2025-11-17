"""
Similarity Search Service
Provides high-level interface for finding similar incidents and patterns
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import json

from rag.vector_db_manager import VectorDBManager
from rag.incident_embeddings import IncidentEmbeddingService


class SimilaritySearchService:
    """
    High-level service for similarity-based incident search

    Features:
    - Find similar past incidents
    - Find similar findings
    - Filter by time window, severity, services
    - Ranking and scoring
    """

    def __init__(
        self,
        vector_db: VectorDBManager,
        embedding_service: IncidentEmbeddingService
    ):
        """
        Initialize similarity search service

        Args:
            vector_db: Vector database manager
            embedding_service: Embedding service for queries
        """
        self.vector_db = vector_db
        self.embedding_service = embedding_service

    def find_similar_incidents(
        self,
        query_incident: Dict[str, Any],
        n_results: int = 5,
        time_window_days: Optional[int] = None,
        severity_filter: Optional[str] = None,
        service_filter: Optional[List[str]] = None,
        similarity_threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Find similar historical incidents

        Args:
            query_incident: Current incident data
            n_results: Number of similar incidents to return
            time_window_days: Only search incidents within N days (None = all time)
            severity_filter: Filter by severity ("critical", "high", etc.)
            service_filter: Filter by affected services
            similarity_threshold: Minimum similarity score (0-1, cosine similarity)

        Returns:
            List of similar incidents with similarity scores
        """
        # Generate embedding for query incident
        embed_result = self.embedding_service.embed_incident(query_incident)
        query_embedding = embed_result["incident_embedding"]

        # Build metadata filter
        where_filter = {}
        if severity_filter:
            where_filter["severity"] = severity_filter

        # Search for similar incidents
        search_results = self.vector_db.search_similar_incidents(
            query_embedding=query_embedding,
            n_results=n_results * 2,  # Get extra results for filtering
            where=where_filter if where_filter else None
        )

        # Post-process results
        similar_incidents = []

        for idx, (incident_id, distance, document, metadata) in enumerate(zip(
            search_results["ids"],
            search_results["distances"],
            search_results["documents"],
            search_results["metadatas"]
        )):
            # Convert distance to similarity score (cosine: similarity = 1 - distance)
            similarity_score = 1 - distance

            # Apply similarity threshold
            if similarity_score < similarity_threshold:
                continue

            # Apply time window filter
            if time_window_days:
                incident_time = datetime.fromisoformat(metadata.get("timestamp", datetime.utcnow().isoformat()))
                cutoff_time = datetime.utcnow() - timedelta(days=time_window_days)
                if incident_time < cutoff_time:
                    continue

            # Apply service filter
            if service_filter:
                incident_services = json.loads(metadata.get("services", "[]"))
                if not any(service in incident_services for service in service_filter):
                    continue

            # Add to results
            similar_incidents.append({
                "incident_id": metadata.get("incident_id"),
                "similarity_score": round(similarity_score, 4),
                "distance": round(distance, 4),
                "summary": document.get("summary", ""),
                "metadata": metadata,
                "rca_results": document.get("rca_results"),
                "timestamp": metadata.get("timestamp"),
                "rank": idx + 1
            })

            # Stop when we have enough results
            if len(similar_incidents) >= n_results:
                break

        return similar_incidents

    def find_similar_findings(
        self,
        query_text: str,
        n_results: int = 10,
        agent_filter: Optional[str] = None,
        severity_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Find similar findings from past analyses

        Args:
            query_text: Query text describing the finding
            n_results: Number of results
            agent_filter: Filter by agent name
            severity_filter: Filter by severity

        Returns:
            List of similar findings with scores
        """
        # Generate query embedding
        query_embedding = self.embedding_service.generate_embedding(query_text)

        # Build filter
        where_filter = {}
        if agent_filter:
            where_filter["agent"] = agent_filter
        if severity_filter:
            where_filter["severity"] = severity_filter

        # Search
        search_results = self.vector_db.search_similar_findings(
            query_embedding=query_embedding,
            n_results=n_results,
            where=where_filter if where_filter else None
        )

        # Format results
        similar_findings = []
        for idx, (finding_id, distance, document, metadata) in enumerate(zip(
            search_results["ids"],
            search_results["distances"],
            search_results["documents"],
            search_results["metadatas"]
        )):
            similarity_score = 1 - distance

            similar_findings.append({
                "finding_id": metadata.get("finding_id"),
                "similarity_score": round(similarity_score, 4),
                "text": document,
                "metadata": metadata,
                "rank": idx + 1
            })

        return similar_findings

    def find_similar_remediations(
        self,
        query_text: str,
        n_results: int = 10,
        priority_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Find similar remediation plans from past incidents

        Args:
            query_text: Query describing the issue to remediate
            n_results: Number of results
            priority_filter: Filter by priority

        Returns:
            List of similar remediations
        """
        # Generate query embedding
        query_embedding = self.embedding_service.generate_embedding(query_text)

        # Build filter
        where_filter = {}
        if priority_filter:
            where_filter["priority"] = priority_filter

        # Search
        search_results = self.vector_db.search_similar_remediations(
            query_embedding=query_embedding,
            n_results=n_results,
            where=where_filter if where_filter else None
        )

        # Format results
        similar_remediations = []
        for idx, (remediation_id, distance, document, metadata) in enumerate(zip(
            search_results["ids"],
            search_results["distances"],
            search_results["documents"],
            search_results["metadatas"]
        )):
            similarity_score = 1 - distance

            similar_remediations.append({
                "remediation_id": metadata.get("remediation_id"),
                "similarity_score": round(similarity_score, 4),
                "text": document,
                "metadata": metadata,
                "rank": idx + 1
            })

        return similar_remediations

    def get_incident_insights(self, incident_id: str) -> Dict[str, Any]:
        """
        Get comprehensive insights about a stored incident

        Args:
            incident_id: Incident to analyze

        Returns:
            Insights including related incidents, common patterns, etc.
        """
        # Get the incident
        incident = self.vector_db.get_incident_by_id(incident_id)

        if not incident:
            return {"error": "Incident not found"}

        # Find similar incidents
        similar = self.find_similar_incidents(
            query_incident=incident.get("metadata", {}),
            n_results=5
        )

        # Extract common patterns
        common_services = []
        common_errors = []

        for sim_incident in similar:
            if sim_incident.get("metadata"):
                services = json.loads(sim_incident["metadata"].get("services", "[]"))
                common_services.extend(services)

        # Count frequency
        from collections import Counter
        service_counts = Counter(common_services)

        return {
            "incident_id": incident_id,
            "similar_incidents": similar,
            "common_services": dict(service_counts.most_common(5)),
            "total_similar_found": len(similar),
            "insights": {
                "pattern_detected": len(similar) >= 3,
                "recurring_issue": len(similar) >= 5,
                "confidence": "high" if len(similar) >= 3 else "medium" if len(similar) >= 1 else "low"
            }
        }

    def analyze_incident_patterns(
        self,
        service: Optional[str] = None,
        time_window_days: int = 30,
        min_occurrences: int = 2
    ) -> Dict[str, Any]:
        """
        Analyze patterns across incidents

        Args:
            service: Filter by service
            time_window_days: Time window to analyze
            min_occurrences: Minimum occurrences to consider a pattern

        Returns:
            Pattern analysis results
        """
        # This would require more complex analysis
        # For now, return basic stats
        stats = self.vector_db.get_collection_stats()

        return {
            "time_window_days": time_window_days,
            "service_filter": service,
            "total_incidents": stats["incidents"]["count"],
            "total_findings": stats["findings"]["count"],
            "total_remediations": stats["remediations"]["count"],
            "analysis_timestamp": datetime.utcnow().isoformat()
        }
