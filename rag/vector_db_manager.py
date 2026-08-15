"""
Vector Database Manager using ChromaDB
Handles persistent storage of incident embeddings and similarity search
"""

import chromadb
from chromadb.config import Settings
from typing import List, Dict, Any, Optional
import uuid
import json
from datetime import datetime
from pathlib import Path
import shutil
import logging

logger = logging.getLogger(__name__)


class VectorDBManager:
    """
    Manages ChromaDB vector database for incident embeddings

    Features:
    - Persistent storage of incident embeddings
    - Collection management (incidents, findings, logs)
    - Metadata filtering and search
    - Automatic embedding generation
    """

    def __init__(self, persist_directory: str = "./chroma_db"):
        """
        Initialize ChromaDB client with persistent storage

        Args:
            persist_directory: Directory to persist ChromaDB data
        """
        self.persist_directory = Path(persist_directory)
        self.persist_directory.mkdir(parents=True, exist_ok=True)

        # Initialize ChromaDB client with persistence
        self.client = chromadb.PersistentClient(
            path=str(self.persist_directory),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )

        # Initialize collections
        self._init_collections()

    def _init_collections(self):
        """Initialize or get existing collections"""

        # Incidents collection - stores full incident reports
        self.incidents_collection = self.client.get_or_create_collection(
            name="incidents",
            metadata={
                "description": "Historical incident data with RCA results",
                "hnsw:space": "cosine"  # Use cosine similarity
            }
        )

        # Findings collection - stores individual findings
        self.findings_collection = self.client.get_or_create_collection(
            name="findings",
            metadata={
                "description": "Individual findings from agent analysis",
                "hnsw:space": "cosine"
            }
        )

        # Remediations collection - stores remediation plans
        self.remediations_collection = self.client.get_or_create_collection(
            name="remediations",
            metadata={
                "description": "Remediation plans and actions",
                "hnsw:space": "cosine"
            }
        )

    def add_incident(
        self,
        incident_id: str,
        incident_summary: str,
        embedding: List[float],
        metadata: Dict[str, Any],
        rca_results: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Add incident to vector database

        Args:
            incident_id: Unique incident identifier
            incident_summary: Text summary of incident for embedding
            embedding: Pre-computed embedding vector
            metadata: Incident metadata (services, severity, timestamp, etc.)
            rca_results: Full RCA analysis results

        Returns:
            Document ID in ChromaDB
        """
        doc_id = f"incident_{incident_id}"

        # Prepare metadata (ChromaDB requires string/int/float values)
        chroma_metadata = {
            "incident_id": incident_id,
            "timestamp": metadata.get("incident_time", datetime.utcnow().isoformat()),
            "severity": metadata.get("severity", "unknown"),
            "services": json.dumps(metadata.get("affected_services", [])),
            "status": metadata.get("status", "resolved"),
            "has_rca": "true" if rca_results else "false"
        }

        # Store full document
        document = {
            "summary": incident_summary,
            "metadata": metadata,
            "rca_results": rca_results
        }

        self.incidents_collection.add(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[json.dumps(document)],
            metadatas=[chroma_metadata]
        )

        return doc_id

    def add_finding(
        self,
        finding_id: str,
        finding_text: str,
        embedding: List[float],
        metadata: Dict[str, Any]
    ) -> str:
        """
        Add individual finding to vector database

        Args:
            finding_id: Unique finding identifier
            finding_text: Text description of finding
            embedding: Pre-computed embedding vector
            metadata: Finding metadata (agent, severity, type, etc.)

        Returns:
            Document ID in ChromaDB
        """
        doc_id = f"finding_{finding_id}"

        chroma_metadata = {
            "finding_id": finding_id,
            "agent": metadata.get("agent_name", "unknown"),
            "severity": metadata.get("severity", "unknown"),
            "type": metadata.get("type", "unknown"),
            "timestamp": metadata.get("timestamp", datetime.utcnow().isoformat())
        }

        self.findings_collection.add(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[finding_text],
            metadatas=[chroma_metadata]
        )

        return doc_id

    def add_remediation(
        self,
        remediation_id: str,
        remediation_text: str,
        embedding: List[float],
        metadata: Dict[str, Any]
    ) -> str:
        """
        Add remediation plan to vector database

        Args:
            remediation_id: Unique remediation identifier
            remediation_text: Text description of remediation
            embedding: Pre-computed embedding vector
            metadata: Remediation metadata

        Returns:
            Document ID in ChromaDB
        """
        doc_id = f"remediation_{remediation_id}"

        chroma_metadata = {
            "remediation_id": remediation_id,
            "incident_id": metadata.get("incident_id", "unknown"),
            "priority": metadata.get("priority", "medium"),
            "status": metadata.get("status", "planned"),
            "timestamp": metadata.get("timestamp", datetime.utcnow().isoformat())
        }

        self.remediations_collection.add(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[remediation_text],
            metadatas=[chroma_metadata]
        )

        return doc_id

    def search_similar_incidents(
        self,
        query_embedding: List[float],
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Search for similar incidents using vector similarity

        Args:
            query_embedding: Query embedding vector
            n_results: Number of results to return
            where: Optional metadata filter (e.g., {"severity": "critical"})

        Returns:
            Dictionary with ids, distances, documents, and metadatas
        """
        results = self.incidents_collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where,
            include=["documents", "metadatas", "distances"]
        )

        # Parse documents back to dict
        parsed_results = {
            "ids": results["ids"][0] if results["ids"] else [],
            "distances": results["distances"][0] if results["distances"] else [],
            "documents": [],
            "metadatas": results["metadatas"][0] if results["metadatas"] else []
        }

        if results["documents"] and results["documents"][0]:
            for doc_str in results["documents"][0]:
                try:
                    parsed_results["documents"].append(json.loads(doc_str))
                except json.JSONDecodeError:
                    parsed_results["documents"].append({"raw": doc_str})

        return parsed_results

    def search_similar_findings(
        self,
        query_embedding: List[float],
        n_results: int = 10,
        where: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Search for similar findings"""
        results = self.findings_collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where,
            include=["documents", "metadatas", "distances"]
        )

        return {
            "ids": results["ids"][0] if results["ids"] else [],
            "distances": results["distances"][0] if results["distances"] else [],
            "documents": results["documents"][0] if results["documents"] else [],
            "metadatas": results["metadatas"][0] if results["metadatas"] else []
        }

    def search_similar_remediations(
        self,
        query_embedding: List[float],
        n_results: int = 10,
        where: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Search for similar remediation plans"""
        results = self.remediations_collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where,
            include=["documents", "metadatas", "distances"]
        )

        return {
            "ids": results["ids"][0] if results["ids"] else [],
            "distances": results["distances"][0] if results["distances"] else [],
            "documents": results["documents"][0] if results["documents"] else [],
            "metadatas": results["metadatas"][0] if results["metadatas"] else []
        }

    def get_incident_by_id(self, incident_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve incident by ID"""
        doc_id = f"incident_{incident_id}"

        try:
            result = self.incidents_collection.get(
                ids=[doc_id],
                include=["documents", "metadatas"]
            )

            if result["ids"]:
                doc = json.loads(result["documents"][0])
                doc["metadata_chroma"] = result["metadatas"][0]
                return doc

            return None

        except Exception:
            return None

    def delete_incident(self, incident_id: str) -> bool:
        """Delete incident from database"""
        doc_id = f"incident_{incident_id}"

        try:
            self.incidents_collection.delete(ids=[doc_id])
            return True
        except Exception:
            return False

    def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about all collections"""
        return {
            "incidents": {
                "count": self.incidents_collection.count(),
                "name": self.incidents_collection.name
            },
            "findings": {
                "count": self.findings_collection.count(),
                "name": self.findings_collection.name
            },
            "remediations": {
                "count": self.remediations_collection.count(),
                "name": self.remediations_collection.name
            },
            "persist_directory": str(self.persist_directory)
        }

    def reset_database(self):
        """Reset all collections (use with caution!)"""
        self.client.reset()
        self._init_collections()
    
    def create_backup(self, backup_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a backup of the entire ChromaDB database
        
        Args:
            backup_path: Optional custom backup path. If not provided,
                        creates backup in ./backups/chroma_{timestamp}
        
        Returns:
            Dictionary with backup information
        """
        if backup_path is None:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            backup_path = f"./backups/chroma_{timestamp}"
        
        backup_dir = Path(backup_path)
        backup_dir.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            # Copy entire ChromaDB directory
            shutil.copytree(self.persist_directory, backup_dir)
            
            # Get backup size
            backup_size_bytes = sum(
                f.stat().st_size for f in backup_dir.rglob('*') if f.is_file()
            )
            backup_size_mb = backup_size_bytes / (1024 * 1024)
            
            # Get collection stats
            stats = self.get_collection_stats()
            
            logger.info(f"Backup created at {backup_dir}, size: {backup_size_mb:.2f}MB")
            
            return {
                "success": True,
                "backup_path": str(backup_dir),
                "size_mb": round(backup_size_mb, 2),
                "timestamp": datetime.utcnow().isoformat(),
                "collections": stats
            }
            
        except Exception as e:
            logger.error(f"Backup failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def export_all(self) -> Dict[str, Any]:
        """
        Export all data from ChromaDB as JSON
        
        Returns:
            Dictionary containing all collections data
        """
        try:
            export_data = {
                "export_timestamp": datetime.utcnow().isoformat(),
                "collections": {}
            }
            
            # Export incidents
            incidents_data = self.incidents_collection.get(
                include=["embeddings", "documents", "metadatas"]
            )
            export_data["collections"]["incidents"] = {
                "count": len(incidents_data["ids"]),
                "data": incidents_data
            }
            
            # Export findings
            findings_data = self.findings_collection.get(
                include=["embeddings", "documents", "metadatas"]
            )
            export_data["collections"]["findings"] = {
                "count": len(findings_data["ids"]),
                "data": findings_data
            }
            
            # Export remediations
            remediations_data = self.remediations_collection.get(
                include=["embeddings", "documents", "metadatas"]
            )
            export_data["collections"]["remediations"] = {
                "count": len(remediations_data["ids"]),
                "data": remediations_data
            }
            
            logger.info(f"Export completed: {export_data['collections']['incidents']['count']} incidents")
            
            return export_data
            
        except Exception as e:
            logger.error(f"Export failed: {e}")
            return {
                "error": str(e)
            }
    
    def import_all(self, import_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Import data into ChromaDB from JSON export
        
        Args:
            import_data: Dictionary containing exported collection data
        
        Returns:
            Import statistics
        """
        try:
            stats = {
                "incidents_imported": 0,
                "findings_imported": 0,
                "remediations_imported": 0,
                "errors": []
            }
            
            # Import incidents
            if "incidents" in import_data.get("collections", {}):
                inc_data = import_data["collections"]["incidents"]["data"]
                if inc_data["ids"]:
                    self.incidents_collection.add(
                        ids=inc_data["ids"],
                        embeddings=inc_data.get("embeddings"),
                        documents=inc_data.get("documents"),
                        metadatas=inc_data.get("metadatas")
                    )
                    stats["incidents_imported"] = len(inc_data["ids"])
            
            # Import findings
            if "findings" in import_data.get("collections", {}):
                find_data = import_data["collections"]["findings"]["data"]
                if find_data["ids"]:
                    self.findings_collection.add(
                        ids=find_data["ids"],
                        embeddings=find_data.get("embeddings"),
                        documents=find_data.get("documents"),
                        metadatas=find_data.get("metadatas")
                    )
                    stats["findings_imported"] = len(find_data["ids"])
            
            # Import remediations
            if "remediations" in import_data.get("collections", {}):
                rem_data = import_data["collections"]["remediations"]["data"]
                if rem_data["ids"]:
                    self.remediations_collection.add(
                        ids=rem_data["ids"],
                        embeddings=rem_data.get("embeddings"),
                        documents=rem_data.get("documents"),
                        metadatas=rem_data.get("metadatas")
                    )
                    stats["remediations_imported"] = len(rem_data["ids"])
            
            logger.info(f"Import completed: {stats}")
            
            return stats
            
        except Exception as e:
            logger.error(f"Import failed: {e}")
            return {
                "error": str(e)
            }
    
    def restore_from_backup(self, backup_path: str) -> Dict[str, Any]:
        """
        Restore ChromaDB from a backup directory
        
        Args:
            backup_path: Path to backup directory
        
        Returns:
            Restore status information
        """
        backup_dir = Path(backup_path)
        
        if not backup_dir.exists():
            return {
                "success": False,
                "error": f"Backup directory not found: {backup_path}"
            }
        
        # Stage the restore next to the live directory, then swap. Deleting the
        # live database first means a failed copy (disk full, permissions,
        # corrupt backup) destroys the knowledge base with no way back.
        parent = self.persist_directory.parent
        staging_dir = parent / f".{self.persist_directory.name}.restore_{uuid.uuid4().hex[:8]}"
        retired_dir = parent / f".{self.persist_directory.name}.old_{uuid.uuid4().hex[:8]}"

        try:
            # 1. Copy the backup into staging and verify it opens.
            shutil.copytree(backup_dir, staging_dir)

            probe = chromadb.PersistentClient(
                path=str(staging_dir),
                settings=Settings(anonymized_telemetry=False, allow_reset=True)
            )
            probe.list_collections()
            del probe

            # 2. Release our handle on the live store before moving it.
            self.client = None

            # 3. Swap: retire current, promote staging.
            if self.persist_directory.exists():
                shutil.move(str(self.persist_directory), str(retired_dir))
            try:
                shutil.move(str(staging_dir), str(self.persist_directory))
            except Exception:
                # Roll back to the retired copy so we never end up with nothing.
                if retired_dir.exists() and not self.persist_directory.exists():
                    shutil.move(str(retired_dir), str(self.persist_directory))
                raise

            # 4. Reinitialize against the restored directory.
            self.__init__(str(self.persist_directory))
            stats = self.get_collection_stats()

            # 5. Only now discard the previous database.
            if retired_dir.exists():
                shutil.rmtree(retired_dir, ignore_errors=True)

            logger.info(f"Restore completed from {backup_path}")

            return {
                "success": True,
                "backup_path": str(backup_dir),
                "timestamp": datetime.utcnow().isoformat(),
                "collections": stats
            }

        except Exception as e:
            logger.error(f"Restore failed: {e}")
            # Leave the live database untouched; clean up staging only.
            shutil.rmtree(staging_dir, ignore_errors=True)
            return {
                "success": False,
                "error": str(e)
            }
