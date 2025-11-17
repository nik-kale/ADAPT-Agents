# RAG & Historical Learning (v3.3)

**Added in:** v3.3.0
**Modules:** `rag/`, `api/knowledge_base_routes.py`

## Overview

ADAPT-Agents uses Retrieval-Augmented Generation (RAG) to learn from every incident. The system automatically stores successful RCA analyses in a vector database (ChromaDB) and retrieves similar past incidents to enhance future analyses—making the AI smarter with every incident.

## Key Features

- **Automatic learning** - Every successful RCA is stored automatically
- **Semantic search** - Find similar incidents using AI embeddings
- **Zero-cost embeddings** - Uses local sentence-transformers (no API calls)
- **RAG-enhanced LLM prompts** - Injects relevant historical context
- **Pattern detection** - Identifies recurring incident patterns
- **Persistent storage** - ChromaDB with disk persistence

## Architecture

```
┌───────────────────────────────────────────┐
│         Incident Analysis                  │
│    (Current RCA Execution)                 │
└──────────────┬────────────────────────────┘
               │
               ↓
┌───────────────────────────────────────────┐
│     Incident Embedding Service             │
│  sentence-transformers (384-dim vectors)   │
└──────────────┬────────────────────────────┘
               │
               ↓
┌───────────────────────────────────────────┐
│         ChromaDB Vector Database           │
│  Collections: incidents, findings, remeds  │
└──────────────┬────────────────────────────┘
               │
               ↓
┌───────────────────────────────────────────┐
│      Similarity Search Service             │
│   (Cosine similarity + filtering)          │
└──────────────┬────────────────────────────┘
               │
               ↓
┌───────────────────────────────────────────┐
│          RAG Enhancer                      │
│  (Inject context into LLM prompts)         │
└───────────────────────────────────────────┘
```

## Components

### 1. Vector Database Manager
**File:** `rag/vector_db_manager.py`

Manages ChromaDB persistence with three collections:
- **incidents** - Full incident reports with RCA results
- **findings** - Individual findings from agents
- **remediations** - Remediation plans and actions

```python
from rag import VectorDBManager

# Initialize
vector_db = VectorDBManager(persist_directory="./chroma_db")

# Store incident
vector_db.add_incident(
    incident_id="inc-123",
    incident_summary="Payment service memory leak after deployment",
    embedding=embedding_vector,
    metadata={
        "incident_time": "2025-01-15T10:00:00Z",
        "affected_services": ["payment-service"],
        "severity": "critical"
    },
    rca_results=rca_analysis_results
)

# Search similar incidents
similar = vector_db.search_similar_incidents(
    query_embedding=current_incident_embedding,
    n_results=5,
    where={"severity": "critical"}  # Optional filter
)

# Get statistics
stats = vector_db.get_collection_stats()
print(f"Total incidents stored: {stats['incidents']['count']}")
```

### 2. Incident Embedding Service
**File:** `rag/incident_embeddings.py`

Generates semantic embeddings using sentence-transformers:

```python
from rag import IncidentEmbeddingService

# Initialize (uses all-MiniLM-L6-v2 model)
embedding_service = IncidentEmbeddingService(
    embedding_model="sentence-transformers",
    cache_enabled=True
)

# Embed incident
embed_result = embedding_service.embed_incident({
    "incident_time": "2025-01-15T10:00:00Z",
    "affected_services": ["api-service"],
    "logs": [...],
    "metrics": [...],
    "changes": [...]
})

# Returns:
{
    "incident_summary": "Incident Time: 2025-01-15T10:00:00Z | Affected Services: api-service | Error Logs: OutOfMemoryError...",
    "incident_embedding": [0.123, -0.456, ...],  # 384 dimensions
    "embedding_model": "sentence-transformers",
    "embedding_dim": 384
}

# Embed finding
finding_embed = embedding_service.embed_finding({
    "description": "Memory leak in payment processor",
    "severity": "high",
    "type": "performance"
})

# Embed remediation
remediation_embed = embedding_service.embed_remediation({
    "action": "Rollback deployment to v1.2.3",
    "priority": "immediate",
    "estimated_time": "15 minutes"
})
```

### 3. Similarity Search Service
**File:** `rag/similarity_search.py`

High-level interface for finding similar incidents:

```python
from rag import SimilaritySearchService

# Initialize
similarity_search = SimilaritySearchService(vector_db, embedding_service)

# Find similar incidents
similar_incidents = similarity_search.find_similar_incidents(
    query_incident=current_incident,
    n_results=5,
    time_window_days=30,      # Last 30 days
    severity_filter="critical",
    similarity_threshold=0.7   # 70% similarity minimum
)

# Returns:
[
    {
        "incident_id": "inc-100",
        "similarity_score": 0.92,  # 92% similar
        "summary": "Payment service OOM after deployment",
        "metadata": {
            "incident_time": "2025-01-10T14:00:00Z",
            "severity": "critical",
            "affected_services": ["payment-service"]
        },
        "rca_results": {
            "root_cause": "Memory leak in new feature",
            "remediation": "Rolled back deployment"
        },
        "rank": 1
    },
    ...
]

# Get incident insights
insights = similarity_search.get_incident_insights("inc-123")

# Returns:
{
    "incident_id": "inc-123",
    "similar_incidents": [...],  # Top 5 similar
    "common_services": {
        "payment-service": 3,
        "api-gateway": 2
    },
    "insights": {
        "pattern_detected": true,    # 3+ similar incidents
        "recurring_issue": true,     # 5+ similar incidents
        "confidence": "high"
    }
}
```

### 4. RAG Enhancer
**File:** `rag/rag_enhancer.py`

Enhances LLM prompts with historical context:

```python
from rag import RAGEnhancer

# Initialize
rag_enhancer = RAGEnhancer(similarity_search, max_context_incidents=3)

# Enhance hypothesis generation prompt
enhanced_prompt = rag_enhancer.enhance_hypothesis_generation(
    current_incident=incident_data,
    phase1_findings=phase1_results,
    base_prompt="Generate root cause hypotheses based on..."
)

# Enhanced prompt includes:
"""
### Historical Context from Similar Incidents
Found 3 similar past incidents for context:

**Similar Incident #1** (Similarity: 92.3%)
- Incident ID: inc-100
- Time: 2025-01-10T14:00:00Z
- Summary: Payment service OOM after deployment
- Root Cause: Memory leak in new user profile feature
- Remediation: Rollback to v1.2.3

**Similar Incident #2** (Similarity: 87.1%)
...

**Guidance:**
- Use the above historical incidents to inform your analysis
- Look for similar patterns, root causes, and remediation strategies
- If the current incident closely matches a past one, reference it
--------------------------------------------------------------------------------

[Original base prompt here]
"""

# Enhance remediation planning
enhanced_remediation_prompt = rag_enhancer.enhance_remediation_planning(
    current_incident=incident_data,
    validated_hypothesis=hypothesis,
    base_prompt="Create remediation plan..."
)
```

## API Endpoints

### Store Incident
```bash
POST /api/v1/knowledge-base/incidents
```

**Request:**
```json
{
  "incident_data": {
    "incident_time": "2025-01-15T10:00:00Z",
    "affected_services": ["payment-service"],
    "logs": [...],
    "metrics": [...],
    "changes": [...]
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

**Response:**
```json
{
  "incident_id": "abc-123",
  "message": "Incident stored successfully in knowledge base",
  "embeddings_generated": true,
  "findings_stored": 3,
  "embedding_model": "sentence-transformers",
  "embedding_dim": 384
}
```

**Note:** This happens automatically after each successful RCA analysis!

### Search Similar Incidents
```bash
POST /api/v1/knowledge-base/search/similar-incidents
```

**Request:**
```json
{
  "incident_data": {
    "incident_time": "2025-01-15T10:00:00Z",
    "affected_services": ["payment-service"],
    "logs": [...]
  },
  "n_results": 5,
  "time_window_days": 30,
  "severity_filter": "critical",
  "similarity_threshold": 0.7
}
```

**Response:**
```json
{
  "total_results": 3,
  "similar_incidents": [
    {
      "incident_id": "inc-100",
      "similarity_score": 0.92,
      "summary": "Payment service OOM",
      "metadata": {...},
      "rca_results": {...},
      "rank": 1
    }
  ],
  "search_params": {
    "n_results": 5,
    "similarity_threshold": 0.7
  }
}
```

### Get Incident Insights
```bash
GET /api/v1/knowledge-base/incidents/{incident_id}/insights
```

**Response:**
```json
{
  "incident_id": "inc-123",
  "similar_incidents": [...],
  "common_services": {
    "payment-service": 3,
    "api-gateway": 2
  },
  "total_similar_found": 3,
  "insights": {
    "pattern_detected": true,
    "recurring_issue": false,
    "confidence": "high"
  }
}
```

### Get Knowledge Base Statistics
```bash
GET /api/v1/knowledge-base/stats
```

**Response:**
```json
{
  "database": {
    "incidents": {"count": 150, "name": "incidents"},
    "findings": {"count": 450, "name": "findings"},
    "remediations": {"count": 300, "name": "remediations"}
  },
  "embedding_cache": {
    "cache_enabled": true,
    "cache_size": 50,
    "embedding_model": "sentence-transformers",
    "embedding_dim": 384
  },
  "rag_config": {
    "max_context_incidents": 3,
    "total_incidents_available": 150,
    "rag_enabled": true
  }
}
```

## Automatic Learning Flow

Every successful RCA analysis is automatically stored:

```python
# In api/server.py:

async def run_analysis(...):
    # Execute RCA
    results = await orchestrator.execute_rca_chain(incident_data)

    # Store results in database
    db.update_analysis_status(analysis_id, "completed", results)

    # Automatic knowledge base storage
    if results.get("success", False):
        await _store_in_knowledge_base(analysis_id, incident_data, results)
        # ↑ This happens automatically!

    # Returns stored incident ID for future similarity searches
```

## Use Cases

### 1. Pattern Detection
Identify recurring incidents:

```bash
curl http://localhost:8000/api/v1/knowledge-base/incidents/inc-123/insights \
  -H "X-API-Key: demo-key-12345"

# Response shows:
# - 5 similar incidents in the past month
# - All involve payment-service
# - Pattern detected: recurring memory leak
```

### 2. Faster Root Cause Analysis
LLM gets context from past incidents:

```python
# Hypothesis generator automatically receives:
"""
### Historical Context
**Similar Incident #1** (92% similar):
Root Cause: Memory leak in user profile feature
Remediation: Rolled back deployment, added memory profiling
"""
# ↑ Helps LLM generate better hypotheses faster
```

### 3. Proven Remediation Strategies
Learn what worked before:

```python
# Remediation planner sees:
"""
### Successful Past Remediations
1. Rollback deployment to previous version (Priority: immediate, Time: 15min)
2. Increase JVM heap size from 2GB to 4GB (Priority: short-term, Time: 10min)
3. Add memory leak detection to CI/CD (Priority: long-term, Time: 2 days)
"""
```

### 4. Team Knowledge Preservation
Never lose tribal knowledge:

```bash
# Search for all incidents involving a specific service
curl -X POST http://localhost:8000/api/v1/knowledge-base/search/similar-incidents \
  -d '{"incident_data": {"affected_services": ["payment-service"]}, "n_results": 100}'

# Get complete history and patterns for that service
```

## Performance

### Embedding Generation
- **Model:** all-MiniLM-L6-v2 (384 dimensions)
- **Speed:** ~5ms per incident on CPU
- **Batch processing:** Supported for bulk operations
- **Caching:** Enabled by default (MD5 hash of text)

### Vector Search
- **Algorithm:** HNSW (Hierarchical Navigable Small World)
- **Similarity metric:** Cosine similarity
- **Query speed:** <10ms for collections up to 100K incidents
- **Scaling:** ChromaDB handles millions of vectors

### Storage
- **Disk usage:** ~1KB per incident (embedding + metadata)
- **Compression:** Enabled by default
- **Persistence:** SQLite backend (cross-platform)

## Configuration

### Custom Embedding Model
```python
# Use OpenAI embeddings instead of local
embedding_service = IncidentEmbeddingService(
    embedding_model="openai",
    cache_enabled=True
)
# Requires: OPENAI_API_KEY environment variable
# Cost: $0.0001 per 1K tokens (~$0.01 per 100 incidents)
```

### Adjust RAG Context Size
```python
# Include more or fewer past incidents in prompts
rag_enhancer = RAGEnhancer(
    similarity_search,
    max_context_incidents=5  # Default: 3
)
```

### Similarity Threshold
```python
# Adjust minimum similarity for matches
similar = similarity_search.find_similar_incidents(
    query_incident=incident,
    similarity_threshold=0.8  # 80% similar (more strict)
    # Default: 0.7 (70%)
)
```

## Monitoring

### Check Database Growth
```bash
# Get stats
curl http://localhost:8000/api/v1/knowledge-base/stats \
  -H "X-API-Key: demo-key-12345"

# Monitor disk usage
du -sh ./chroma_db
```

### Test Similarity Search
```bash
# Store a test incident
curl -X POST http://localhost:8000/api/v1/knowledge-base/incidents \
  -H "X-API-Key: demo-key-12345" \
  -d @test_incident.json

# Search for it
curl -X POST http://localhost:8000/api/v1/knowledge-base/search/similar-incidents \
  -H "X-API-Key: demo-key-12345" \
  -d '{"incident_data": ..., "n_results": 5}'

# Should return the test incident with 100% similarity
```

## Best Practices

1. **Let it learn** - Don't delete old incidents; they're training data
2. **Quality over quantity** - Ensure incident data is complete and accurate
3. **Regular cleanup** - Archive very old incidents (>1 year) periodically
4. **Monitor similarity scores** - Scores <0.5 are likely unrelated
5. **Use filters** - Narrow searches with severity/time/service filters

## Troubleshooting

### No Similar Incidents Found
- Knowledge base may be empty (first incidents)
- Incident data may be too sparse
- Lower similarity_threshold (try 0.5 instead of 0.7)
- Check if embeddings are being generated

### Poor Similarity Matches
- Incident summaries too generic
- Missing critical fields (logs, metrics, changes)
- Different terminology used in past incidents
- Try adjusting time_window_days

### Slow Searches
- Large collection (>100K incidents)
- Consider upgrading ChromaDB hardware
- Enable query result caching
- Reduce n_results

## Next Steps

- Learn about [Enterprise Integrations](integrations.md)
- Explore [Interactive Visualizations](visualizations.md)
- Check [API Reference](api_reference.md)
