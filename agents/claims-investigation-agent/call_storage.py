"""
Call Storage Layer using PostgreSQL

Stores call records, summaries, and transcripts for MCP server retrieval.
Uses PostgreSQL for robust, multi-service access.
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional
from contextlib import contextmanager

from loguru import logger

try:
    import psycopg2
except ImportError:
    logger.error("psycopg2 not installed. Install with: pip install psycopg2-binary")
    raise ImportError("psycopg2-binary is required for PostgreSQL support")


class CallStorage:
    """PostgreSQL storage for call records and summaries."""

    def __init__(self, database_url: Optional[str] = None):
        """
        Initialize PostgreSQL storage.
        
        Args:
            database_url: PostgreSQL connection string (e.g., postgresql://user:pass@host:port/db)
                         If None, reads from DATABASE_URL environment variable
        """
        self.database_url = database_url or os.getenv("DATABASE_URL")
        
        if not self.database_url:
            raise ValueError(
                "DATABASE_URL is required for PostgreSQL storage. "
                "Set it in your environment or docker-compose.yml"
            )
        
        logger.info("📊 Initializing PostgreSQL storage")
        logger.info(f"   • Connection: {self._safe_connection_string()}")
        
        self._init_database()

    def _safe_connection_string(self) -> str:
        """Return connection string with password masked."""
        try:
            # postgresql://user:pass@host:port/db
            parts = self.database_url.split('@')
            if len(parts) == 2:
                user_pass = parts[0].split('//')[-1]
                if ':' in user_pass:
                    user = user_pass.split(':')[0]
                    return f"postgresql://{user}:***@{parts[1]}"
            return "postgresql://***"
        except:
            return "postgresql://***"

    def _init_database(self):
        """Create PostgreSQL tables if they don't exist."""
        logger.info("🔧 Creating database schema...")
        
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS calls (
                        call_sid VARCHAR(255) PRIMARY KEY,
                        phone_number VARCHAR(50) NOT NULL,
                        langgraph_url TEXT,
                        assistant_name VARCHAR(255),
                        status VARCHAR(50) NOT NULL DEFAULT 'initiated',
                        start_time TIMESTAMP NOT NULL,
                        end_time TIMESTAMP,
                        duration_seconds INTEGER,
                        transcript TEXT,
                        outcome JSONB,
                        cost DECIMAL(10, 4),
                        metadata JSONB,
                        created_at TIMESTAMP NOT NULL,
                        updated_at TIMESTAMP NOT NULL
                    )
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_status ON calls(status)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_start_time ON calls(start_time)
                """)
                conn.commit()
                logger.info("✅ PostgreSQL database schema ready")

    @contextmanager
    def _get_connection(self):
        """Context manager for PostgreSQL connections."""
        conn = psycopg2.connect(self.database_url)
        try:
            yield conn
        finally:
            conn.close()

    def create_call(
        self,
        call_sid: str,
        phone_number: str,
        langgraph_url: Optional[str] = None,
        assistant_name: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> Dict:
        """Create a new call record in PostgreSQL."""
        now = datetime.utcnow()
        
        logger.info(f"💾 Saving call to PostgreSQL database:")
        logger.info(f"   • Call SID: {call_sid}")
        logger.info(f"   • Phone: {phone_number}")
        logger.info(f"   • LangGraph URL: {langgraph_url}")
        logger.info(f"   • Assistant: {assistant_name}")
        logger.info(f"   • Metadata: {metadata}")

        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO calls (
                        call_sid, phone_number, langgraph_url, assistant_name,
                        status, start_time, metadata, created_at, updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                    (
                        call_sid,
                        phone_number,
                        langgraph_url,
                        assistant_name,
                        "initiated",
                        now,
                        json.dumps(metadata or {}),
                        now,
                        now,
                    ),
                )
                conn.commit()

        logger.info(f"✅ Call record saved to PostgreSQL: {call_sid}")
        return self.get_call(call_sid)

    def update_call_status(self, call_sid: str, status: str) -> bool:
        """Update call status in PostgreSQL."""
        now = datetime.utcnow()
        
        logger.info(f"💾 Updating call status in PostgreSQL: {call_sid} → {status}")

        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE calls
                    SET status = %s, updated_at = %s
                    WHERE call_sid = %s
                """,
                    (status, now, call_sid),
                )
                conn.commit()
                success = cursor.rowcount > 0
        
        if success:
            logger.info(f"✅ Status updated in PostgreSQL: {call_sid}")
        else:
            logger.warning(f"⚠️  Call not found in PostgreSQL: {call_sid}")
        
        return success

    def complete_call(
        self,
        call_sid: str,
        transcript: Optional[str] = None,
        outcome: Optional[Dict] = None,
        duration_seconds: Optional[int] = None,
        cost: Optional[float] = None,
    ) -> bool:
        """Mark call as completed and store results in PostgreSQL."""
        now = datetime.utcnow()
        
        logger.info(f"💾 Completing call in PostgreSQL:")
        logger.info(f"   • Call SID: {call_sid}")
        logger.info(f"   • Duration: {duration_seconds}s")
        logger.info(f"   • Transcript length: {len(transcript) if transcript else 0} chars")
        logger.info(f"   • Outcome: {outcome}")

        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE calls
                    SET status = %s,
                        end_time = %s,
                        duration_seconds = %s,
                        transcript = %s,
                        outcome = %s,
                        cost = %s,
                        updated_at = %s
                    WHERE call_sid = %s
                """,
                    (
                        "completed",
                        now,
                        duration_seconds,
                        transcript,
                        json.dumps(outcome or {}),
                        cost,
                        now,
                        call_sid,
                    ),
                )
                conn.commit()
                success = cursor.rowcount > 0

        if success:
            logger.info(f"✅ Call completed and saved to PostgreSQL: {call_sid}")
        else:
            logger.warning(f"⚠️  Call not found in PostgreSQL: {call_sid}")
        
        return success

    def get_call(self, call_sid: str) -> Optional[Dict]:
        """Get a call record by SID from PostgreSQL."""
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM calls WHERE call_sid = %s", (call_sid,)
                )
                row = cursor.fetchone()
                if not row:
                    logger.debug(f"Call not found in PostgreSQL: {call_sid}")
                    return None
                # Get column names
                columns = [desc[0] for desc in cursor.description]
                result = dict(zip(columns, row))
                logger.debug(f"Retrieved call from PostgreSQL: {call_sid}, status={result.get('status')}")
                return result

    def list_calls(
        self,
        limit: int = 100,
        status: Optional[str] = None,
        order_by: str = "start_time",
        ascending: bool = False,
    ) -> List[Dict]:
        """List calls from PostgreSQL with optional filtering."""
        query = "SELECT * FROM calls"
        params = []

        if status:
            query += " WHERE status = %s"
            params.append(status)

        order_direction = "ASC" if ascending else "DESC"
        query += f" ORDER BY {order_by} {order_direction} LIMIT %s"
        params.append(limit)
        
        logger.info(f"📋 Querying PostgreSQL: limit={limit}, status={status}")

        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, params)
                rows = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]
                results = [dict(zip(columns, row)) for row in rows]
                
        logger.info(f"✅ Retrieved {len(results)} calls from PostgreSQL")
        return results

    def get_call_summary(self, call_sid: str) -> Optional[Dict]:
        """Get a formatted summary of a call from PostgreSQL."""
        logger.info(f"📖 Retrieving call summary from PostgreSQL: {call_sid}")
        
        call = self.get_call(call_sid)
        if not call:
            logger.warning(f"⚠️  Call summary not found: {call_sid}")
            return None

        # Parse JSON fields (PostgreSQL JSONB might already be dict)
        outcome = call.get("outcome", {})
        if isinstance(outcome, str):
            outcome = json.loads(outcome) if outcome else {}
        
        metadata = call.get("metadata", {})
        if isinstance(metadata, str):
            metadata = json.loads(metadata) if metadata else {}

        # Convert timestamps to ISO format if they're datetime objects (PostgreSQL returns datetime)
        start_time = call.get("start_time")
        if hasattr(start_time, 'isoformat'):
            start_time = start_time.isoformat()
        
        end_time = call.get("end_time")
        if end_time and hasattr(end_time, 'isoformat'):
            end_time = end_time.isoformat()

        summary = {
            "call_sid": call["call_sid"],
            "phone_number": call["phone_number"],
            "status": call["status"],
            "start_time": start_time,
            "end_time": end_time,
            "duration_seconds": call.get("duration_seconds"),
            "transcript": call.get("transcript"),
            "outcome": outcome,
            "cost": float(call["cost"]) if call.get("cost") else None,
            "assistant_name": call.get("assistant_name"),
            "langgraph_url": call.get("langgraph_url"),
            "metadata": metadata,
        }
        
        logger.info(f"✅ Call summary retrieved: {call_sid}, status={summary['status']}")
        return summary

    def delete_call(self, call_sid: str) -> bool:
        """Delete a call record from PostgreSQL."""
        logger.info(f"🗑️  Deleting call from PostgreSQL: {call_sid}")
        
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM calls WHERE call_sid = %s", (call_sid,)
                )
                conn.commit()
                success = cursor.rowcount > 0
        
        if success:
            logger.info(f"✅ Call deleted from PostgreSQL: {call_sid}")
        else:
            logger.warning(f"⚠️  Call not found for deletion: {call_sid}")
        
        return success


# Singleton instance
_storage = None


def get_storage(database_url: Optional[str] = None) -> CallStorage:
    """Get or create the PostgreSQL storage singleton.
    
    Args:
        database_url: PostgreSQL connection string. If None, checks DATABASE_URL env var.
    
    Raises:
        ValueError: If DATABASE_URL is not set
    """
    global _storage
    if _storage is None:
        database_url = database_url or os.getenv("DATABASE_URL")
        _storage = CallStorage(database_url=database_url)
    return _storage

