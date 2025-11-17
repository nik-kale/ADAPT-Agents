"""
Incident Embedding Service
Generates semantic embeddings for incidents, findings, and logs
"""

from typing import List, Dict, Any, Optional
import hashlib
import json
from datetime import datetime


class IncidentEmbeddingService:
    """
    Generates embeddings for incident data

    Supports:
    - Sentence-BERT embeddings (local, free)
    - OpenAI embeddings (API-based, high quality)
    - Caching for efficiency
    """

    def __init__(self, embedding_model: str = "sentence-transformers", cache_enabled: bool = True):
        """
        Initialize embedding service

        Args:
            embedding_model: 'sentence-transformers' or 'openai'
            cache_enabled: Enable embedding caching
        """
        self.embedding_model = embedding_model
        self.cache_enabled = cache_enabled
        self._embedding_cache: Dict[str, List[float]] = {}

        # Initialize embedding model
        self._init_model()

    def _init_model(self):
        """Initialize the embedding model"""
        if self.embedding_model == "sentence-transformers":
            try:
                from sentence_transformers import SentenceTransformer
                # Use all-MiniLM-L6-v2: 384 dimensions, fast, good quality
                self.model = SentenceTransformer('all-MiniLM-L6-v2')
                self.embedding_dim = 384
            except ImportError:
                raise ImportError(
                    "sentence-transformers not installed. "
                    "Install with: pip install sentence-transformers"
                )

        elif self.embedding_model == "openai":
            try:
                import openai
                self.openai = openai
                self.embedding_dim = 1536  # text-embedding-3-small
            except ImportError:
                raise ImportError(
                    "openai not installed. "
                    "Install with: pip install openai"
                )

        else:
            raise ValueError(f"Unsupported embedding model: {self.embedding_model}")

    def _get_cache_key(self, text: str) -> str:
        """Generate cache key from text"""
        return hashlib.md5(text.encode()).hexdigest()

    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for a single text

        Args:
            text: Input text to embed

        Returns:
            Embedding vector as list of floats
        """
        # Check cache
        if self.cache_enabled:
            cache_key = self._get_cache_key(text)
            if cache_key in self._embedding_cache:
                return self._embedding_cache[cache_key]

        # Generate embedding
        if self.embedding_model == "sentence-transformers":
            embedding = self.model.encode(text, convert_to_numpy=True).tolist()

        elif self.embedding_model == "openai":
            response = self.openai.embeddings.create(
                model="text-embedding-3-small",
                input=text
            )
            embedding = response.data[0].embedding

        # Cache result
        if self.cache_enabled:
            self._embedding_cache[cache_key] = embedding

        return embedding

    def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts (batch processing)

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        if self.embedding_model == "sentence-transformers":
            embeddings = self.model.encode(texts, convert_to_numpy=True).tolist()
            return embeddings

        elif self.embedding_model == "openai":
            # OpenAI supports batch embeddings
            response = self.openai.embeddings.create(
                model="text-embedding-3-small",
                input=texts
            )
            return [item.embedding for item in response.data]

    def embed_incident(self, incident_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create embeddings for an incident

        Generates:
        - Main incident summary embedding
        - Individual log embeddings (if many logs, sample)
        - Metrics summary embedding

        Args:
            incident_data: Full incident data

        Returns:
            Dictionary with embeddings and incident summary text
        """
        # Create incident summary text
        summary_parts = []

        # Add incident metadata
        if "incident_time" in incident_data:
            summary_parts.append(f"Incident Time: {incident_data['incident_time']}")

        if "affected_services" in incident_data:
            services = ", ".join(incident_data["affected_services"])
            summary_parts.append(f"Affected Services: {services}")

        # Add log summary
        if "logs" in incident_data and incident_data["logs"]:
            logs = incident_data["logs"]
            # Take first 10 error logs
            error_logs = [log for log in logs if log.get("level") == "ERROR"][:10]
            if error_logs:
                log_messages = " | ".join([log.get("message", "") for log in error_logs])
                summary_parts.append(f"Error Logs: {log_messages}")

        # Add metrics summary
        if "metrics" in incident_data and incident_data["metrics"]:
            metrics = incident_data["metrics"]
            metric_names = ", ".join([m.get("name", "") for m in metrics[:5]])
            summary_parts.append(f"Key Metrics: {metric_names}")

        # Add change summary
        if "changes" in incident_data and incident_data["changes"]:
            changes = incident_data["changes"]
            change_types = ", ".join([c.get("type", "") for c in changes[:5]])
            summary_parts.append(f"Recent Changes: {change_types}")

        incident_summary = " | ".join(summary_parts)

        # Generate embedding
        embedding = self.generate_embedding(incident_summary)

        return {
            "incident_summary": incident_summary,
            "incident_embedding": embedding,
            "embedding_model": self.embedding_model,
            "embedding_dim": self.embedding_dim,
            "timestamp": datetime.utcnow().isoformat()
        }

    def embed_finding(self, finding: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create embedding for a single finding

        Args:
            finding: Finding data

        Returns:
            Dictionary with embedding and finding text
        """
        # Create finding text
        finding_parts = []

        if "description" in finding:
            finding_parts.append(finding["description"])

        if "details" in finding:
            finding_parts.append(str(finding["details"]))

        if "severity" in finding:
            finding_parts.append(f"Severity: {finding['severity']}")

        if "type" in finding:
            finding_parts.append(f"Type: {finding['type']}")

        finding_text = " | ".join(finding_parts)

        # Generate embedding
        embedding = self.generate_embedding(finding_text)

        return {
            "finding_text": finding_text,
            "finding_embedding": embedding,
            "embedding_model": self.embedding_model,
            "embedding_dim": self.embedding_dim
        }

    def embed_remediation(self, remediation: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create embedding for a remediation plan

        Args:
            remediation: Remediation data

        Returns:
            Dictionary with embedding and remediation text
        """
        remediation_parts = []

        if "action" in remediation:
            remediation_parts.append(remediation["action"])

        if "description" in remediation:
            remediation_parts.append(remediation["description"])

        if "steps" in remediation and isinstance(remediation["steps"], list):
            steps_text = " -> ".join(remediation["steps"][:5])
            remediation_parts.append(f"Steps: {steps_text}")

        if "priority" in remediation:
            remediation_parts.append(f"Priority: {remediation['priority']}")

        remediation_text = " | ".join(remediation_parts)

        # Generate embedding
        embedding = self.generate_embedding(remediation_text)

        return {
            "remediation_text": remediation_text,
            "remediation_embedding": embedding,
            "embedding_model": self.embedding_model,
            "embedding_dim": self.embedding_dim
        }

    def embed_rca_results(self, rca_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create comprehensive embeddings for full RCA results

        Generates embeddings for:
        - Overall RCA summary
        - Individual findings from each phase
        - Hypothesis
        - Remediation plan

        Args:
            rca_results: Complete RCA analysis results

        Returns:
            Dictionary with multiple embeddings
        """
        embeddings = {}

        # Embed hypothesis if present
        if "phase2" in rca_results and "hypothesis_generator" in rca_results["phase2"]:
            hypothesis = rca_results["phase2"]["hypothesis_generator"]
            if hasattr(hypothesis, "findings") and hypothesis.findings:
                for idx, finding in enumerate(hypothesis.findings[:3]):  # Top 3 hypotheses
                    finding_dict = finding.dict() if hasattr(finding, "dict") else finding
                    embed_result = self.embed_finding(finding_dict)
                    embeddings[f"hypothesis_{idx}"] = embed_result

        # Embed remediation if present
        if "phase3" in rca_results and "remediation_planner" in rca_results["phase3"]:
            remediation = rca_results["phase3"]["remediation_planner"]
            if hasattr(remediation, "findings") and remediation.findings:
                for idx, finding in enumerate(remediation.findings[:3]):
                    finding_dict = finding.dict() if hasattr(finding, "dict") else finding
                    embed_result = self.embed_remediation(finding_dict)
                    embeddings[f"remediation_{idx}"] = embed_result

        return embeddings

    def clear_cache(self):
        """Clear embedding cache"""
        self._embedding_cache.clear()

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return {
            "cache_enabled": self.cache_enabled,
            "cache_size": len(self._embedding_cache),
            "embedding_model": self.embedding_model,
            "embedding_dim": self.embedding_dim
        }
