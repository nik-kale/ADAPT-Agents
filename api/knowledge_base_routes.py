"""
Knowledge Base Management API Routes
Provides endpoints for RAG system and incident learning
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from typing import List, Dict, Optional, Any
import uuid

from rag import VectorDBManager, IncidentEmbeddingService, SimilaritySearchService, RAGEnhancer


router = APIRouter()

# Initialize RAG components (singleton pattern)
_vector_db = None
_embedding_service = None
_similarity_search = None
_rag_enhancer = None


def get_rag_components():
    """Initialize and return RAG components (lazy initialization)"""
    global _vector_db, _embedding_service, _similarity_search, _rag_enhancer

    if _vector_db is None:
        _vector_db = VectorDBManager(persist_directory="./chroma_db")

    if _embedding_service is None:
        try:
            # Try sentence-transformers first (free, local)
            _embedding_service = IncidentEmbeddingService(
                embedding_model="sentence-transformers",
                cache_enabled=True
            )
        except ImportError:
            raise HTTPException(
                status_code=500,
                detail="RAG system not configured. Install sentence-transformers: pip install sentence-transformers"
            )

    if _similarity_search is None:
        _similarity_search = SimilaritySearchService(_vector_db, _embedding_service)

    if _rag_enhancer is None:
        _rag_enhancer = RAGEnhancer(_similarity_search, max_context_incidents=3)

    return {
        "vector_db": _vector_db,
        "embedding_service": _embedding_service,
        "similarity_search": _similarity_search,
        "rag_enhancer": _rag_enhancer
    }


# Pydantic models
class IncidentStorageRequest(BaseModel):
    """Request to store incident in knowledge base"""
    incident_id: Optional[str] = None
    incident_data: Dict[str, Any]
    rca_results: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


class SimilarIncidentsRequest(BaseModel):
    """Request to find similar incidents"""
    incident_data: Dict[str, Any]
    n_results: int = 5
    time_window_days: Optional[int] = None
    severity_filter: Optional[str] = None
    similarity_threshold: float = 0.7


class SimilarFindingsRequest(BaseModel):
    """Request to find similar findings"""
    query_text: str
    n_results: int = 10
    agent_filter: Optional[str] = None
    severity_filter: Optional[str] = None


@router.post("/knowledge-base/incidents", tags=["knowledge-base"])
async def store_incident(
    request: IncidentStorageRequest,
    api_key: str = Depends(lambda: "demo-key-12345")  # Use real auth
):
    """
    Store incident in knowledge base for future similarity search

    This endpoint:
    1. Generates embeddings for the incident
    2. Stores in ChromaDB vector database
    3. Enables future RAG-enhanced analysis

    Example:
    ```json
    {
        "incident_data": {
            "incident_time": "2025-01-15T10:00:00Z",
            "affected_services": ["api-service"],
            "logs": [...],
            "metrics": [...]
        },
        "rca_results": {
            "phase1": {...},
            "phase2": {...},
            "phase3": {...}
        },
        "metadata": {
            "severity": "critical",
            "status": "resolved"
        }
    }
    ```
    """
    try:
        components = get_rag_components()
        vector_db = components["vector_db"]
        embedding_service = components["embedding_service"]

        # Generate incident ID if not provided
        incident_id = request.incident_id or str(uuid.uuid4())

        # Generate embeddings
        embed_result = embedding_service.embed_incident(request.incident_data)

        # Prepare metadata
        metadata = request.metadata or {}
        metadata["incident_time"] = request.incident_data.get("incident_time", "")
        metadata["affected_services"] = request.incident_data.get("affected_services", [])
        metadata["severity"] = metadata.get("severity", "unknown")
        metadata["status"] = metadata.get("status", "unknown")

        # Store in vector database
        doc_id = vector_db.add_incident(
            incident_id=incident_id,
            incident_summary=embed_result["incident_summary"],
            embedding=embed_result["incident_embedding"],
            metadata=metadata,
            rca_results=request.rca_results
        )

        # Also store individual findings if RCA results present
        findings_stored = 0
        if request.rca_results:
            # Store Phase 2 findings (hypotheses)
            if "phase2" in request.rca_results and "hypothesis_generator" in request.rca_results["phase2"]:
                hyp = request.rca_results["phase2"]["hypothesis_generator"]
                if hasattr(hyp, "findings") and hyp.findings:
                    for finding in hyp.findings[:3]:  # Top 3
                        finding_dict = finding.dict() if hasattr(finding, "dict") else finding
                        finding_embed = embedding_service.embed_finding(finding_dict)

                        vector_db.add_finding(
                            finding_id=str(uuid.uuid4()),
                            finding_text=finding_embed["finding_text"],
                            embedding=finding_embed["finding_embedding"],
                            metadata={
                                "agent_name": "HypothesisGeneratorAgent",
                                "incident_id": incident_id,
                                "severity": finding_dict.get("severity", "unknown"),
                                "type": "hypothesis"
                            }
                        )
                        findings_stored += 1

        return {
            "incident_id": incident_id,
            "doc_id": doc_id,
            "message": "Incident stored successfully in knowledge base",
            "embeddings_generated": True,
            "findings_stored": findings_stored,
            "embedding_model": embed_result["embedding_model"],
            "embedding_dim": embed_result["embedding_dim"]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to store incident: {str(e)}")


@router.post("/knowledge-base/search/similar-incidents", tags=["knowledge-base"])
async def search_similar_incidents(
    request: SimilarIncidentsRequest,
    api_key: str = Depends(lambda: "demo-key-12345")
):
    """
    Find similar historical incidents using semantic search

    Returns incidents that are semantically similar to the query incident,
    along with their RCA results and similarity scores.

    Use this to:
    - Learn from past incidents
    - Find known solutions
    - Identify patterns
    - Speed up root cause analysis
    """
    try:
        components = get_rag_components()
        similarity_search = components["similarity_search"]

        # Find similar incidents
        similar_incidents = similarity_search.find_similar_incidents(
            query_incident=request.incident_data,
            n_results=request.n_results,
            time_window_days=request.time_window_days,
            severity_filter=request.severity_filter,
            similarity_threshold=request.similarity_threshold
        )

        return {
            "query_summary": "Semantic search completed",
            "total_results": len(similar_incidents),
            "similar_incidents": similar_incidents,
            "search_params": {
                "n_results": request.n_results,
                "time_window_days": request.time_window_days,
                "severity_filter": request.severity_filter,
                "similarity_threshold": request.similarity_threshold
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.post("/knowledge-base/search/similar-findings", tags=["knowledge-base"])
async def search_similar_findings(
    request: SimilarFindingsRequest,
    api_key: str = Depends(lambda: "demo-key-12345")
):
    """
    Find similar findings from past agent analyses

    Search through historical findings to find patterns and insights
    from past RCA analyses.
    """
    try:
        components = get_rag_components()
        similarity_search = components["similarity_search"]

        similar_findings = similarity_search.find_similar_findings(
            query_text=request.query_text,
            n_results=request.n_results,
            agent_filter=request.agent_filter,
            severity_filter=request.severity_filter
        )

        return {
            "query_text": request.query_text,
            "total_results": len(similar_findings),
            "similar_findings": similar_findings
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/knowledge-base/incidents/{incident_id}", tags=["knowledge-base"])
async def get_incident(
    incident_id: str,
    api_key: str = Depends(lambda: "demo-key-12345")
):
    """
    Retrieve incident from knowledge base by ID

    Returns the stored incident with its RCA results and metadata.
    """
    try:
        components = get_rag_components()
        vector_db = components["vector_db"]

        incident = vector_db.get_incident_by_id(incident_id)

        if not incident:
            raise HTTPException(status_code=404, detail="Incident not found in knowledge base")

        return {
            "incident_id": incident_id,
            "incident": incident
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve incident: {str(e)}")


@router.get("/knowledge-base/incidents/{incident_id}/insights", tags=["knowledge-base"])
async def get_incident_insights(
    incident_id: str,
    api_key: str = Depends(lambda: "demo-key-12345")
):
    """
    Get comprehensive insights about a stored incident

    Returns:
    - Similar incidents
    - Common patterns
    - Recurring issues
    - Confidence metrics
    """
    try:
        components = get_rag_components()
        similarity_search = components["similarity_search"]

        insights = similarity_search.get_incident_insights(incident_id)

        if "error" in insights:
            raise HTTPException(status_code=404, detail=insights["error"])

        return insights

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get insights: {str(e)}")


@router.delete("/knowledge-base/incidents/{incident_id}", tags=["knowledge-base"])
async def delete_incident(
    incident_id: str,
    api_key: str = Depends(lambda: "demo-key-12345")
):
    """
    Delete incident from knowledge base

    Permanently removes the incident and its embeddings.
    """
    try:
        components = get_rag_components()
        vector_db = components["vector_db"]

        success = vector_db.delete_incident(incident_id)

        if not success:
            raise HTTPException(status_code=404, detail="Incident not found")

        return {
            "incident_id": incident_id,
            "message": "Incident deleted successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete incident: {str(e)}")


@router.get("/knowledge-base/stats", tags=["knowledge-base"])
async def get_knowledge_base_stats(
    api_key: str = Depends(lambda: "demo-key-12345")
):
    """
    Get statistics about the knowledge base

    Returns counts of incidents, findings, and remediations stored.
    """
    try:
        components = get_rag_components()
        vector_db = components["vector_db"]
        embedding_service = components["embedding_service"]
        rag_enhancer = components["rag_enhancer"]

        db_stats = vector_db.get_collection_stats()
        cache_stats = embedding_service.get_cache_stats()
        rag_stats = rag_enhancer.get_enhancement_stats()

        return {
            "database": db_stats,
            "embedding_cache": cache_stats,
            "rag_config": rag_stats,
            "rag_enabled": True
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


@router.post("/knowledge-base/enhance-prompt", tags=["knowledge-base"])
async def enhance_prompt_with_rag(
    incident_data: Dict[str, Any],
    base_prompt: str,
    agent_name: Optional[str] = None,
    api_key: str = Depends(lambda: "demo-key-12345")
):
    """
    Enhance an LLM prompt with RAG context

    Takes a base prompt and enriches it with relevant historical context
    from similar past incidents.

    This is used internally by agents but can also be called directly
    for testing or custom integrations.
    """
    try:
        components = get_rag_components()
        rag_enhancer = components["rag_enhancer"]

        enhanced_prompt = rag_enhancer.enhance_agent_prompt(
            agent_name=agent_name or "GenericAgent",
            current_incident=incident_data,
            base_prompt=base_prompt
        )

        return {
            "enhanced_prompt": enhanced_prompt,
            "original_length": len(base_prompt),
            "enhanced_length": len(enhanced_prompt),
            "context_added": len(enhanced_prompt) - len(base_prompt)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to enhance prompt: {str(e)}")
