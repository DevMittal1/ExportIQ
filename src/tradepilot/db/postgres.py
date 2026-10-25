"""PostgreSQL storage layer for LangGraph checkpoints, chat threads, messages, and dossiers."""

import os
import json
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime
from psycopg_pool import ConnectionPool
from langgraph.checkpoint.postgres import PostgresSaver

from ..config import settings

logger = logging.getLogger(__name__)

_pool: Optional[ConnectionPool] = None
_checkpointer: Optional[PostgresSaver] = None


def get_postgres_pool() -> Optional[ConnectionPool]:
    """Get or create singleton PostgreSQL connection pool."""
    global _pool
    if _pool is not None:
        return _pool
    
    db_url = settings.DATABASE_URL or os.getenv("DATABASE_URL")
    if not db_url:
        logger.warning("DATABASE_URL not configured. PostgreSQL persistence disabled.")
        return None
        
    try:
        _pool = ConnectionPool(
            conninfo=db_url,
            max_size=10,
            kwargs={"autocommit": True}
        )
        logger.info("PostgreSQL connection pool initialized.")
        return _pool
    except Exception as e:
        logger.error(f"Failed to initialize PostgreSQL pool: {e}")
        return None


class DualPostgresSaver(PostgresSaver):
    """PostgresSaver with both synchronous and asynchronous support via thread offloading."""

    async def aget_tuple(self, config: Any) -> Any:
        import asyncio
        return await asyncio.to_thread(self.get_tuple, config)

    async def aput(self, config: Any, checkpoint: Any, metadata: Any, new_versions: Any) -> Any:
        import asyncio
        return await asyncio.to_thread(self.put, config, checkpoint, metadata, new_versions)

    async def aput_writes(self, config: Any, writes: Any, task_id: Any, task_path: str = "") -> Any:
        import asyncio
        return await asyncio.to_thread(self.put_writes, config, writes, task_id, task_path)

    async def alist(self, config: Optional[Any], *, filter: Optional[Any] = None, before: Optional[Any] = None, limit: Optional[int] = None) -> Any:
        import asyncio
        return await asyncio.to_thread(lambda: list(self.list(config, filter=filter, before=before, limit=limit)))


def get_postgres_checkpointer() -> Optional[DualPostgresSaver]:
    """Get or initialize singleton PostgresSaver for LangGraph."""
    global _checkpointer
    if _checkpointer is not None:
        return _checkpointer
        
    pool = get_postgres_pool()
    if not pool:
        return None
        
    try:
        _checkpointer = DualPostgresSaver(pool)
        _checkpointer.setup()
        logger.info("LangGraph PostgresSaver checkpointer initialized & schema verified.")
        return _checkpointer
    except Exception as e:
        logger.error(f"Failed to setup PostgresSaver: {e}")
        return None


def init_application_tables() -> bool:
    """Initialize relational tables for conversation histories, messages, and dossiers."""
    pool = get_postgres_pool()
    if not pool:
        return False
        
    create_schema_sql = """
    CREATE TABLE IF NOT EXISTS chat_threads (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW(),
        metadata JSONB DEFAULT '{}'::jsonb
    );

    CREATE TABLE IF NOT EXISTS chat_messages (
        id TEXT PRIMARY KEY,
        thread_id TEXT NOT NULL REFERENCES chat_threads(id) ON DELETE CASCADE,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        hitl_action JSONB DEFAULT NULL,
        created_at TIMESTAMPTZ DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS trade_dossiers (
        id TEXT PRIMARY KEY,
        thread_id TEXT REFERENCES chat_threads(id) ON DELETE CASCADE,
        product TEXT NOT NULL,
        report JSONB NOT NULL,
        created_at TIMESTAMPTZ DEFAULT NOW()
    );

    CREATE INDEX IF NOT EXISTS idx_chat_messages_thread_id ON chat_messages(thread_id, created_at ASC);
    CREATE INDEX IF NOT EXISTS idx_chat_threads_updated_at ON chat_threads(updated_at DESC);
    CREATE INDEX IF NOT EXISTS idx_trade_dossiers_product ON trade_dossiers(product);
    """
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(create_schema_sql)
        logger.info("TradePilot chat & dossier tables initialized in PostgreSQL.")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize PostgreSQL application tables: {e}")
        return False


def db_save_thread(thread_id: str, title: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
    """Create or update a chat thread record."""
    pool = get_postgres_pool()
    if not pool:
        return False
    meta_json = json.dumps(metadata or {})
    query = """
    INSERT INTO chat_threads (id, title, updated_at, metadata)
    VALUES (%s, %s, NOW(), %s::jsonb)
    ON CONFLICT (id) DO UPDATE SET
        title = EXCLUDED.title,
        updated_at = NOW(),
        metadata = chat_threads.metadata || EXCLUDED.metadata;
    """
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (thread_id, title, meta_json))
        return True
    except Exception as e:
        logger.error(f"Error saving thread {thread_id}: {e}")
        return False


def db_list_threads(limit: int = 50) -> List[Dict[str, Any]]:
    """Retrieve recent chat threads ordered by most recent activity."""
    pool = get_postgres_pool()
    if not pool:
        return []
    query = """
    SELECT id, title, created_at, updated_at, metadata
    FROM chat_threads
    ORDER BY updated_at DESC
    LIMIT %s;
    """
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (limit,))
                rows = cur.fetchall()
                return [
                    {
                        "id": row[0],
                        "title": row[1],
                        "created_at": row[2].isoformat() if row[2] else None,
                        "updated_at": row[3].isoformat() if row[3] else None,
                        "metadata": row[4] or {}
                    }
                    for row in rows
                ]
    except Exception as e:
        logger.error(f"Error listing threads: {e}")
        return []


def db_get_thread_messages(thread_id: str) -> List[Dict[str, Any]]:
    """Retrieve chronological messages for a specific thread."""
    pool = get_postgres_pool()
    if not pool:
        return []
    query = """
    SELECT id, role, content, hitl_action, created_at
    FROM chat_messages
    WHERE thread_id = %s
    ORDER BY created_at ASC;
    """
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (thread_id,))
                rows = cur.fetchall()
                return [
                    {
                        "id": row[0],
                        "role": row[1],
                        "content": row[2],
                        "hitl_action": row[3],
                        "created_at": row[4].isoformat() if row[4] else None
                    }
                    for row in rows
                ]
    except Exception as e:
        logger.error(f"Error getting messages for thread {thread_id}: {e}")
        return []


def db_save_message(
    msg_id: str,
    thread_id: str,
    role: str,
    content: str,
    hitl_action: Optional[Dict[str, Any]] = None
) -> bool:
    """Save a chat message with optional HITL card action payload."""
    pool = get_postgres_pool()
    if not pool:
        return False
    hitl_json = json.dumps(hitl_action) if hitl_action else None
    query = """
    INSERT INTO chat_messages (id, thread_id, role, content, hitl_action)
    VALUES (%s, %s, %s, %s, %s::jsonb)
    ON CONFLICT (id) DO UPDATE SET
        content = EXCLUDED.content,
        hitl_action = EXCLUDED.hitl_action;
    """
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (msg_id, thread_id, role, content, hitl_json))
        return True
    except Exception as e:
        logger.error(f"Error saving message {msg_id}: {e}")
        return False


def db_save_dossier(dossier_id: str, thread_id: Optional[str], product: str, report: Dict[str, Any]) -> bool:
    """Save finalized export market dossier JSON."""
    pool = get_postgres_pool()
    if not pool:
        return False
    report_json = json.dumps(report)
    query = """
    INSERT INTO trade_dossiers (id, thread_id, product, report)
    VALUES (%s, %s, %s, %s::jsonb)
    ON CONFLICT (id) DO UPDATE SET
        report = EXCLUDED.report;
    """
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (dossier_id, thread_id, product, report_json))
        return True
    except Exception as e:
        logger.error(f"Error saving dossier {dossier_id}: {e}")
        return False


def db_delete_thread(thread_id: str) -> bool:
    """Delete a thread and all associated messages."""
    pool = get_postgres_pool()
    if not pool:
        return False
    query = "DELETE FROM chat_threads WHERE id = %s;"
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (thread_id,))
        return True
    except Exception as e:
        logger.error(f"Error deleting thread {thread_id}: {e}")
        return False
