"""
OstraClaw — Base Types
Modelos compartilhados entre todas as skills de auditoria.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class SkillStatus(str, Enum):
    APPROVED = "APPROVED"      # Documento aprovado
    CAUTION = "CAUTION"        # Inconsistências leves — requer revisão humana
    SUSPECT = "SUSPECT"        # Alta probabilidade de fraude — quarentena
    UNKNOWN = "UNKNOWN"        # Não foi possível determinar
    ERROR = "ERROR"            # Erro durante a execução da skill


class AuditResult(BaseModel):
    """Resultado padronizado de uma skill de auditoria."""
    skill: str
    status: SkillStatus
    score: float = Field(ge=0.0, le=1.0)
    detail: str
    evidence: dict[str, Any] = Field(default_factory=dict)
    timestamp: str
    hash_sha256: Optional[str] = None

    @property
    def is_critical(self) -> bool:
        return self.status == SkillStatus.SUSPECT and self.score < 0.3
