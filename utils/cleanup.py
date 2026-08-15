"""
Data Retention and Cleanup Utility

Automatically cleans up old analyses and embeddings based on retention policy.
"""

import sqlite3
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from pathlib import Path
from contextlib import closing

from config.settings import get_settings

logger = logging.getLogger(__name__)


class DataCleanupService:
    """Service for automatic data retention and cleanup"""
    
    def __init__(self, db_path: str = "adapt_agents.db"):
        self.db_path = db_path
        self.settings = get_settings()
        self.cleanup_stats = {
            "last_run": None,
            "total_cleaned": 0,
            "analyses_deleted": 0,
            "embeddings_deleted": 0
        }
    
    async def cleanup_old_analyses(self, retention_days: int = None) -> Dict[str, int]:
        """
        Delete analyses older than retention period
        
        Args:
            retention_days: Number of days to retain data (defaults to settings)
            
        Returns:
            Dictionary with cleanup statistics
        """
        if retention_days is None:
            retention_days = self.settings.data_retention_days
        
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
        cutoff_timestamp = cutoff_date.isoformat()
        
        logger.info(f"Starting cleanup: retention_days={retention_days}, cutoff={cutoff_timestamp}")
        
        try:
            # `with` commits/rolls back the transaction but does not close the
            # handle, so closing is handled by the outer contextlib.closing.
            with closing(sqlite3.connect(self.db_path)) as conn, conn:
                cursor = conn.cursor()

                # Find old analyses
                cursor.execute("""
                    SELECT id, created_at FROM analyses
                    WHERE created_at < ?
                    ORDER BY created_at ASC
                    LIMIT ?
                """, (cutoff_timestamp, self.settings.cleanup_batch_size))

                old_analyses = cursor.fetchall()
                analysis_ids = [row[0] for row in old_analyses]

                if not analysis_ids:
                    logger.info("No old analyses to clean up")
                    return {"deleted": 0, "child_rows_deleted": 0, "cutoff_date": cutoff_timestamp}

                placeholders = ','.join('?' * len(analysis_ids))

                # Delete dependent rows first. SQLite does not enforce foreign
                # keys by default, so agent_executions rows would otherwise be
                # orphaned forever and grow without bound.
                cursor.execute(f"""
                    DELETE FROM agent_executions WHERE analysis_id IN ({placeholders})
                """, analysis_ids)
                child_deleted = cursor.rowcount

                # Delete the parent analyses
                cursor.execute(f"""
                    DELETE FROM analyses WHERE id IN ({placeholders})
                """, analysis_ids)
                deleted_count = cursor.rowcount

            # Update stats
            self.cleanup_stats["analyses_deleted"] += deleted_count
            self.cleanup_stats["total_cleaned"] += deleted_count
            self.cleanup_stats["last_run"] = datetime.utcnow().isoformat()

            logger.info(
                f"Cleanup completed: deleted {deleted_count} analyses and "
                f"{child_deleted} agent_execution rows older than {cutoff_timestamp}"
            )

            return {
                "deleted": deleted_count,
                "child_rows_deleted": child_deleted,
                "cutoff_date": cutoff_timestamp,
                "analysis_ids": analysis_ids[:10]  # Return first 10 for logging
            }

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            raise
    
    async def cleanup_orphaned_embeddings(self) -> Dict[str, int]:
        """
        Clean up ChromaDB embeddings for deleted analyses
        
        Returns:
            Dictionary with cleanup statistics
        """
        try:
            # Import ChromaDB
            try:
                import chromadb
            except ImportError:
                logger.warning("ChromaDB not available, skipping embedding cleanup")
                return {"deleted": 0, "reason": "chromadb_not_installed"}
            
            # Get valid analysis IDs from database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM analyses")
            valid_ids = set(row[0] for row in cursor.fetchall())
            conn.close()
            
            # Check ChromaDB collections
            client = chromadb.PersistentClient(path="./chroma_db")
            collections = client.list_collections()
            
            deleted_count = 0
            
            for collection in collections:
                # Collection names might be based on analysis IDs
                # This is a placeholder - actual implementation depends on RAG structure
                logger.info(f"Checking collection: {collection.name}")
                # TODO: Implement orphan detection based on actual RAG schema
            
            logger.info(f"Embedding cleanup completed: {deleted_count} embeddings deleted")
            
            self.cleanup_stats["embeddings_deleted"] += deleted_count
            
            return {"deleted": deleted_count}
            
        except Exception as e:
            logger.error(f"Error during embedding cleanup: {e}")
            return {"deleted": 0, "error": str(e)}
    
    async def get_database_size(self) -> Dict[str, Any]:
        """Get database size statistics"""
        try:
            db_file = Path(self.db_path)
            if not db_file.exists():
                return {"size_mb": 0, "exists": False}
            
            size_bytes = db_file.stat().st_size
            size_mb = size_bytes / (1024 * 1024)
            
            # Get row counts
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM analyses")
            analysis_count = cursor.fetchone()[0]
            conn.close()
            
            # Get ChromaDB size
            chroma_path = Path("./chroma_db")
            chroma_size_mb = 0
            if chroma_path.exists():
                chroma_size_bytes = sum(
                    f.stat().st_size for f in chroma_path.rglob('*') if f.is_file()
                )
                chroma_size_mb = chroma_size_bytes / (1024 * 1024)
            
            return {
                "database_size_mb": round(size_mb, 2),
                "chromadb_size_mb": round(chroma_size_mb, 2),
                "total_size_mb": round(size_mb + chroma_size_mb, 2),
                "analysis_count": analysis_count,
                "exists": True
            }
            
        except Exception as e:
            logger.error(f"Error getting database size: {e}")
            return {"error": str(e)}
    
    async def run_full_cleanup(self, retention_days: Optional[int] = None) -> Dict[str, Any]:
        """
        Run complete cleanup process

        Args:
            retention_days: Optional override for the configured retention period.
                            Falls back to settings.data_retention_days when None.
        """
        effective_retention = (
            retention_days if retention_days is not None
            else self.settings.data_retention_days
        )
        logger.info(f"Starting full cleanup process (retention_days={effective_retention})")

        # Get size before cleanup
        size_before = await self.get_database_size()

        # Clean old analyses
        analysis_cleanup = await self.cleanup_old_analyses(retention_days=retention_days)
        
        # Clean orphaned embeddings
        embedding_cleanup = await self.cleanup_orphaned_embeddings()
        
        # Get size after cleanup
        size_after = await self.get_database_size()
        
        space_reclaimed_mb = size_before.get("total_size_mb", 0) - size_after.get("total_size_mb", 0)
        
        result = {
            "timestamp": datetime.utcnow().isoformat(),
            "analyses_deleted": analysis_cleanup.get("deleted", 0),
            "embeddings_deleted": embedding_cleanup.get("deleted", 0),
            "space_reclaimed_mb": round(space_reclaimed_mb, 2),
            "size_before_mb": size_before.get("total_size_mb", 0),
            "size_after_mb": size_after.get("total_size_mb", 0),
            "retention_days": effective_retention
        }
        
        logger.info(f"Full cleanup completed: {result}")
        
        return result
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cleanup statistics"""
        return self.cleanup_stats.copy()


# Global cleanup service instance
_cleanup_service = None


def get_cleanup_service(db_path: str = "adapt_agents.db") -> DataCleanupService:
    """Get or create cleanup service instance"""
    global _cleanup_service
    if _cleanup_service is None:
        _cleanup_service = DataCleanupService(db_path)
    return _cleanup_service


async def scheduled_cleanup_task():
    """Background task for scheduled cleanup"""
    settings = get_settings()
    cleanup_service = get_cleanup_service()
    
    if not settings.enable_auto_cleanup:
        logger.info("Automatic cleanup is disabled")
        return
    
    logger.info(
        f"Scheduled cleanup task started: "
        f"interval={settings.cleanup_schedule_hours}h, "
        f"retention={settings.data_retention_days}d"
    )
    
    while True:
        try:
            # Run cleanup
            result = await cleanup_service.run_full_cleanup()
            logger.info(f"Scheduled cleanup completed: {result}")
            
            # Wait for next run
            await asyncio.sleep(settings.cleanup_schedule_hours * 3600)
            
        except Exception as e:
            logger.error(f"Error in scheduled cleanup: {e}")
            # Wait a bit before retrying
            await asyncio.sleep(3600)  # Retry in 1 hour

