"""Persistent SQLite storage engine for tool execution telemetry, API usage, and budget controls."""

import sqlite3
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from ..config import settings


class UsageDatabase:
    """Manages persistent SQLite storage for tool calls, latency telemetry, and quota budgets."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or (settings.PROJECT_ROOT / "tradepilot_metrics.db")
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initialize database tables and indexes."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Execution Logs Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tool_executions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    call_id TEXT UNIQUE NOT NULL,
                    tool_name TEXT NOT NULL,
                    agent_name TEXT,
                    arguments_json TEXT,
                    result_summary TEXT,
                    status TEXT NOT NULL,
                    duration_ms REAL NOT NULL,
                    error_message TEXT,
                    created_at REAL NOT NULL
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tool_name ON tool_executions(tool_name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON tool_executions(created_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_status ON tool_executions(status)")
            
            # 2. Tool Budget Limits Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tool_budgets (
                    tool_name TEXT PRIMARY KEY,
                    budget_limit INTEGER NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)
            conn.commit()

    def record_execution(
        self,
        call_id: str,
        tool_name: str,
        arguments: Dict[str, Any],
        status: str,
        duration_ms: float,
        agent_name: Optional[str] = None,
        result: Optional[Any] = None,
        error_message: Optional[str] = None
    ):
        """Persist a completed or failed tool call to the database."""
        # Sanitize arguments and summary
        try:
            args_str = json.dumps(arguments, default=str)
        except Exception:
            args_str = str(arguments)

        summary_str = None
        if result is not None:
            if isinstance(result, dict):
                summary_str = f"Status: {result.get('status', 'ok')} | Keys: {list(result.keys())[:5]}"
            else:
                summary_str = str(result)[:200]

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO tool_executions (
                    call_id, tool_name, agent_name, arguments_json, result_summary,
                    status, duration_ms, error_message, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                call_id, tool_name, agent_name, args_str, summary_str,
                status, round(duration_ms, 2), error_message, time.time()
            ))
            conn.commit()

    def set_budget(self, tool_name: str, max_calls: int):
        """Set or update persistent call budget for a tool."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO tool_budgets (tool_name, budget_limit, updated_at)
                VALUES (?, ?, ?)
            """, (tool_name, max_calls, time.time()))
            conn.commit()

    def remove_budget(self, tool_name: str):
        """Remove a budget constraint for a tool."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM tool_budgets WHERE tool_name = ?", (tool_name,))
            conn.commit()

    def get_budgets(self) -> Dict[str, int]:
        """Retrieve all active budget constraints."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT tool_name, budget_limit FROM tool_budgets")
            rows = cursor.fetchall()
            return {row["tool_name"]: row["budget_limit"] for row in rows}

    def check_budget_exceeded(self, tool_name: str) -> Optional[int]:
        """Check if tool call count exceeds its budget. Returns budget limit if exceeded, else None."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT budget_limit FROM tool_budgets WHERE tool_name = ?", (tool_name,))
            row = cursor.fetchone()
            if not row:
                return None
            limit = row["budget_limit"]
            
            cursor.execute("SELECT COUNT(*) as cnt FROM tool_executions WHERE tool_name = ?", (tool_name,))
            count = cursor.fetchone()["cnt"]
            if count >= limit:
                return limit
            return None

    def get_tool_metrics_summary(self) -> Dict[str, Any]:
        """Generate high-level aggregated metrics from persistent records."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Overall totals
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_calls,
                    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successful_calls,
                    SUM(CASE WHEN status != 'success' THEN 1 ELSE 0 END) as failed_calls,
                    AVG(duration_ms) as avg_latency_ms,
                    COUNT(DISTINCT tool_name) as distinct_tools
                FROM tool_executions
            """)
            overall = cursor.fetchone()
            
            # Per-tool breakdown
            cursor.execute("""
                SELECT 
                    tool_name,
                    COUNT(*) as total_calls,
                    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successful_calls,
                    SUM(CASE WHEN status != 'success' THEN 1 ELSE 0 END) as failed_calls,
                    AVG(duration_ms) as avg_latency_ms,
                    MAX(created_at) as last_called_at
                FROM tool_executions
                GROUP BY tool_name
                ORDER BY total_calls DESC
            """)
            tool_rows = cursor.fetchall()
            budgets = self.get_budgets()
            
            tools_data = {}
            for row in tool_rows:
                t_name = row["tool_name"]
                tools_data[t_name] = {
                    "tool_name": t_name,
                    "total_calls": row["total_calls"],
                    "successful_calls": row["successful_calls"] or 0,
                    "failed_calls": row["failed_calls"] or 0,
                    "avg_latency_ms": round(row["avg_latency_ms"] or 0.0, 2),
                    "last_called_at": row["last_called_at"],
                    "budget_limit": budgets.get(t_name)
                }

            total_calls = overall["total_calls"] or 0
            successful_calls = overall["successful_calls"] or 0
            success_rate = round((successful_calls / total_calls * 100), 1) if total_calls > 0 else 100.0

            return {
                "total_tool_invocations": total_calls,
                "total_tool_errors": overall["failed_calls"] or 0,
                "success_rate_percent": success_rate,
                "overall_avg_latency_ms": round(overall["avg_latency_ms"] or 0.0, 2),
                "active_tools_tracked": overall["distinct_tools"] or 0,
                "active_budgets_count": len(budgets),
                "tools": tools_data
            }

    def get_logs(
        self,
        limit: int = 50,
        offset: int = 0,
        tool_name: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve detailed execution log records with optional filtering."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM tool_executions WHERE 1=1"
            params: List[Any] = []
            
            if tool_name:
                query += " AND tool_name = ?"
                params.append(tool_name)
            if status:
                query += " AND status = ?"
                params.append(status)
                
            query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            logs = []
            for r in rows:
                logs.append({
                    "id": r["id"],
                    "call_id": r["call_id"],
                    "tool_name": r["tool_name"],
                    "agent_name": r["agent_name"],
                    "arguments": json.loads(r["arguments_json"]) if r["arguments_json"] else {},
                    "result_summary": r["result_summary"],
                    "status": r["status"],
                    "duration_ms": r["duration_ms"],
                    "error_message": r["error_message"],
                    "created_at": r["created_at"],
                    "created_at_iso": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(r["created_at"]))
                })
            return logs

    def clear_all(self):
        """Purge execution logs and budget records."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM tool_executions")
            cursor.execute("DELETE FROM tool_budgets")
            conn.commit()


# Global DB instance
USAGE_DB = UsageDatabase()
