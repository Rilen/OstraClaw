"""
OstraClaw — Skill: Metadata Extractor
Extrai e analisa metadados do PDF (software de criação, datas, autor, etc.)
para detectar documentos criados fora do fluxo oficial da Imprensa Municipal.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import pypdf
import structlog

from .base import AuditResult, SkillStatus

log = structlog.get_logger(__name__)

# ── Padrões de software legítimo da Imprensa Oficial ────────
_OFFICIAL_CREATORS = [
    "acrobat", "adobe", "pdftk", "libreoffice", "diario", "diário",
    "imprensa", "pmro", "prefeitura", "pdfcreator", "ghostscript", "gs",
    "nitro", "foxit"
]

# ── Softwares que indicam criação NÃO oficial ───────────────
_SUSPICIOUS_CREATORS = [
    "microsoft word", "word", "google docs", "wps", "openoffice writer",
    "canva", "powerpoint", "excel", "notion", "writesonic", "chatgpt",
    "ilovepdf", "smallpdf", "docx2pdf"
]

# ── Regex para detectar datas futuras (impossíveis) ────────
_FUTURE_YEAR = re.compile(r"(202[7-9]|20[3-9]\d|2[1-9]\d{2}|[3-9]\d{3})")


def _classify_software(creator: str) -> tuple[float, str]:
    """
    Retorna (score_confiança, motivo) com base no software de criação.
    Score 1.0 = oficial | 0.5 = desconhecido | 0.0 = suspeito
    """
    creator_lower = creator.lower()

    for sus in _SUSPICIOUS_CREATORS:
        if sus in creator_lower:
            return 0.0, f"Software suspeito detectado: '{creator}'. Documentos oficiais não são criados com este programa."

    for ok in _OFFICIAL_CREATORS:
        if ok in creator_lower:
            return 1.0, f"Software de criação reconhecido como oficial: '{creator}'"

    return 0.5, f"Software desconhecido: '{creator}'. Não está na lista de ferramentas homologadas."


def _check_modification_date(mod_date_str: Optional[str]) -> tuple[float, str]:
    """Verifica se a data de modificação é plausível."""
    if not mod_date_str:
        return 0.5, "Data de modificação ausente nos metadados."

    # pypdf retorna datas no formato D:YYYYMMDDHHmmSS
    match = re.search(r"D:(\d{4})(\d{2})(\d{2})", mod_date_str)
    if match:
        year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
        try:
            doc_date = datetime(year, month, day)
            now = datetime.utcnow()
            if doc_date > now:
                return 0.0, f"⚠️ Data de modificação no FUTURO: {doc_date.date()}. Indica manipulação de metadados."
            if year < 2000:
                return 0.0, f"⚠️ Data de modificação implausível: {doc_date.date()}. Possível adulteração."
            return 1.0, f"Data de modificação plausível: {doc_date.date()}"
        except ValueError:
            return 0.0, f"Data inválida nos metadados: {mod_date_str}"

    return 0.5, f"Não foi possível interpretar a data: {mod_date_str}"


def run(file_path: Path, config: Optional[dict] = None) -> AuditResult:
    """
    Extrai e analisa os metadados do PDF.

    Args:
        file_path: Caminho do arquivo PDF.
        config: Configurações opcionais (padrões personalizados da prefeitura).

    Returns:
        AuditResult com análise dos metadados.
    """
    log.info("skill.metadata.start", file=file_path.name)

    try:
        reader = pypdf.PdfReader(str(file_path))
        meta = reader.metadata or {}

        # Extrair metadados brutos
        raw_meta = {
            "title": meta.get("/Title", ""),
            "author": meta.get("/Author", ""),
            "subject": meta.get("/Subject", ""),
            "creator": meta.get("/Creator", ""),
            "producer": meta.get("/Producer", ""),
            "creation_date": meta.get("/CreationDate", ""),
            "mod_date": meta.get("/ModDate", ""),
            "keywords": meta.get("/Keywords", ""),
            "num_pages": len(reader.pages),
        }

        log.info("skill.metadata.extracted", meta=raw_meta, file=file_path.name)

        issues = []
        alerts = []
        scores = []

        # ── 1. Verificar software de criação ─────────────
        creator = raw_meta["creator"] or raw_meta["producer"] or ""
        if creator:
            score, reason = _classify_software(creator)
            scores.append(score)
            if score < 1.0:
                (alerts if score == 0.0 else issues).append(reason)
            else:
                issues.append(reason)  # Motivo positivo
        else:
            scores.append(0.75) # Neutro: Ausência não é crime
            issues.append("ℹ️ Metadado 'Creator' ausente (comum em digitalização simples).")

        # ── 2. Verificar data de modificação ─────────────
        score_date, reason_date = _check_modification_date(raw_meta["mod_date"])
        scores.append(score_date)
        if score_date < 1.0:
            issues.append(reason_date) # Tratar como observação local
        else:
            issues.append(reason_date)

        # ── 3. Verificar metadados vazios (red flag) ──────
        empty_count = sum(1 for k in ["author", "title", "subject"] if not raw_meta.get(k))
        if empty_count >= 2:
            scores.append(0.7) # Neutro
            issues.append(f"ℹ️ {empty_count} metadados vazios (comum em scripts oficiais).")
        else:
            scores.append(1.0)

        # ── Score final ───────────────────────────────────
        final_score = sum(scores) / len(scores) if scores else 0.5

        if alerts:
            status = SkillStatus.SUSPECT if final_score < 0.5 else SkillStatus.CAUTION
            detail = " | ".join(alerts)
        else:
            status = SkillStatus.APPROVED
            detail = f"Metadados consistentes com documentos oficiais. Creator: '{creator}'"

        return AuditResult(
            skill="metadata_extractor",
            status=status,
            score=round(final_score, 3),
            detail=detail,
            evidence=raw_meta,
            timestamp=datetime.utcnow().isoformat(),
        )

    except pypdf.errors.PdfReadError as e:
        log.error("skill.metadata.pdf_error", error=str(e), file=file_path.name)
        return AuditResult(
            skill="metadata_extractor",
            status=SkillStatus.ERROR,
            score=0.0,
            detail=f"Arquivo PDF corrompido ou ilegível: {e}",
            evidence={"error": str(e)},
            timestamp=datetime.utcnow().isoformat(),
        )
    except Exception as e:
        log.exception("skill.metadata.unexpected_error", file=file_path.name)
        return AuditResult(
            skill="metadata_extractor",
            status=SkillStatus.ERROR,
            score=0.0,
            detail=f"Erro inesperado: {e}",
            evidence={"error": str(e)},
            timestamp=datetime.utcnow().isoformat(),
        )
