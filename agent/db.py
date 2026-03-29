"""
OstraClaw — Database Client
Persiste resultados de auditoria no PostgreSQL e recupera hashes oficiais.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Optional

import structlog
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

log = structlog.get_logger(__name__)


class Database:
    """Interface com o banco de dados PostgreSQL do OstraClaw."""

    def __init__(self, url: Optional[str] = None):
        self.url = url or os.getenv(
            "DATABASE_URL",
            "postgresql://ostraclaw:ostraclaw_secret@ostraclaw_db:5432/ostraclaw"
        )
        self._engine = None
        self._connect()

    def _connect(self) -> None:
        try:
            self._engine = create_engine(self.url, pool_pre_ping=True)
            with self._engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            log.info("db.connected")
        except OperationalError as e:
            log.warning("db.connection_failed", error=str(e))
            self._engine = None

    def get_official_hashes(self) -> list[str]:
        """Retorna lista de SHA-256 de documentos oficiais conhecidos."""
        if not self._engine:
            return []
        try:
            with self._engine.connect() as conn:
                result = conn.execute(text("SELECT sha256 FROM official_hashes"))
                return [row[0] for row in result]
        except Exception as e:
            log.error("db.get_hashes_error", error=str(e))
            return []

    def save_audit(self, report: dict) -> None:
        """Persiste o relatório de auditoria no banco."""
        if not self._engine:
            log.warning("db.save_skipped_no_connection")
            return
        try:
            with self._engine.begin() as conn:
                conn.execute(
                    text("""
                        INSERT INTO audit_log (
                            filename, timestamp, aggregate_score, preliminary_verdict,
                            final_verdict, confidence, main_reason, skill_results, duration_seconds
                        ) VALUES (
                            :filename, :timestamp, :aggregate_score, :preliminary_verdict,
                            :final_verdict, :confidence, :main_reason, :skill_results, :duration_seconds
                        )
                    """),
                    {
                        "filename": report["file"],
                        "timestamp": report["timestamp"],
                        "aggregate_score": report["aggregate_score"],
                        "preliminary_verdict": report["preliminary_verdict"],
                        "final_verdict": report["final_verdict"],
                        "confidence": report["confidence"],
                        "main_reason": report.get("main_reason", ""),
                        "skill_results": json.dumps(report["skill_results"], ensure_ascii=False),
                        "duration_seconds": report["duration_seconds"],
                    }
                )
            log.info("db.audit_saved", file=report["file"])
        except Exception as e:
            log.error("db.save_error", error=str(e))
