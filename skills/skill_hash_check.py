"""
OstraClaw — Skill: Hash Check
Calcula SHA-256 do arquivo e compara com registro oficial no banco.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import structlog

from .base import AuditResult, SkillStatus

log = structlog.get_logger(__name__)


def _sha256(path: Path, chunk_size: int = 65536) -> str:
    """Calcula SHA-256 do arquivo em blocos (eficiente para arquivos grandes)."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


def run(file_path: Path, known_hashes: Optional[list[str]] = None) -> AuditResult:
    """
    Executa a verificação de integridade via hash SHA-256.

    Args:
        file_path: Caminho absoluto para o PDF.
        known_hashes: Lista de hashes oficiais conhecidos (do banco ou arquivo de config).

    Returns:
        AuditResult com status APPROVED, SUSPECT ou UNKNOWN.
    """
    log.info("skill.hash_check.start", file=file_path.name)

    try:
        file_hash = _sha256(file_path)
        log.info("skill.hash_check.computed", hash=file_hash, file=file_path.name)

        # Se não temos base de hashes, não podemos negar — apenas registramos
        if not known_hashes:
            return AuditResult(
                skill="hash_check",
                status=SkillStatus.UNKNOWN,
                score=0.5,
                hash_sha256=file_hash,
                detail="Base de hashes oficiais não configurada. Hash calculado mas não verificado.",
                evidence={"sha256": file_hash},
                timestamp=datetime.utcnow().isoformat(),
            )

        if file_hash in known_hashes:
            return AuditResult(
                skill="hash_check",
                status=SkillStatus.APPROVED,
                score=1.0,
                hash_sha256=file_hash,
                detail=f"Hash SHA-256 confirmado na base oficial: {file_hash}",
                evidence={"sha256": file_hash, "found_in_registry": True},
                timestamp=datetime.utcnow().isoformat(),
            )
        else:
            return AuditResult(
                skill="hash_check",
                status=SkillStatus.SUSPECT,
                score=0.0,
                hash_sha256=file_hash,
                detail=f"⚠️ Hash NÃO encontrado na base oficial: {file_hash}. Arquivo pode ter sido adulterado.",
                evidence={"sha256": file_hash, "found_in_registry": False},
                timestamp=datetime.utcnow().isoformat(),
            )

    except OSError as e:
        log.error("skill.hash_check.error", error=str(e), file=file_path.name)
        return AuditResult(
            skill="hash_check",
            status=SkillStatus.ERROR,
            score=0.0,
            detail=f"Erro ao ler arquivo: {e}",
            evidence={"error": str(e)},
            timestamp=datetime.utcnow().isoformat(),
        )
