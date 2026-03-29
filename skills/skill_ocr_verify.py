"""
OstraClaw — Skill: OCR Verifier
Extrai o texto do PDF via pdfplumber (nativo) com fallback para Tesseract OCR.
Verifica palavras-chave obrigatórias, padrões de formatação e estrutura
esperada dos Jornais Oficiais da PMRO.
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Optional

import pdfplumber
import pytesseract
import structlog
from pdf2image import convert_from_path
from PIL import Image

from .base import AuditResult, SkillStatus

log = structlog.get_logger(__name__)

# ── Palavras-chave obrigatórias no Diário Oficial ────────────
REQUIRED_KEYWORDS = [
    "prefeitura",
    "diário oficial",
    "diario oficial",
    "município",
    "municipio",
]

# ── Palavras-chave de reforço (peso adicional) ───────────────
REINFORCING_KEYWORDS = [
    "portaria",
    "decreto",
    "lei municipal",
    "edital",
    "licitação",
    "licitacao",
    "extrato",
    "gabinete do prefeito",
    "secretaria",
    "CNPJ",
    "CPF",
]

# ── Padrões de brasão/cabeçalho oficial (regex) ─────────────
HEADER_PATTERNS = [
    re.compile(r"pref(ei|i)tura\s+municipal", re.IGNORECASE),
    re.compile(r"di[aá]rio\s+oficial", re.IGNORECASE),
    re.compile(r"ano\s+\w+\s*[–\-]\s*n[°º\.]\s*\d+", re.IGNORECASE),  # "Ano XIV – Nº 1234"
    re.compile(r"\d{1,2}\s+de\s+\w+\s+de\s+20\d{2}", re.IGNORECASE),   # Data por extenso
]

# ── Padrões que indicam origem suspeita (word, docs) ────────
SUSPICIOUS_PATTERNS = [
    re.compile(r"normal\.dotm", re.IGNORECASE),
    re.compile(r"document\s*properties", re.IGNORECASE),
    re.compile(r"created\s+with\s+(word|docs|canva)", re.IGNORECASE),
]


def _extract_text_native(file_path: Path, max_pages: int = 5) -> str:
    """Extrai texto diretamente do PDF (vetorial). Rápido e preciso."""
    text = ""
    try:
        with pdfplumber.open(str(file_path)) as pdf:
            for page in pdf.pages[:max_pages]:
                page_text = page.extract_text() or ""
                text += page_text + "\n"
    except Exception as e:
        log.warning("skill.ocr.native_extract_failed", error=str(e))
    return text.strip()


def _extract_text_ocr(file_path: Path, max_pages: int = 3) -> str:
    """
    Fallback: converte páginas em imagem e aplica Tesseract OCR.
    Usado quando o PDF é escaneado ou sem camada de texto.
    """
    text = ""
    try:
        images = convert_from_path(str(file_path), dpi=200, last_page=max_pages)
        for img in images:
            ocr_text = pytesseract.image_to_string(img, lang="por")
            text += ocr_text + "\n"
    except Exception as e:
        log.warning("skill.ocr.tesseract_failed", error=str(e))
    return text.strip()


def _count_keywords(text: str, keywords: list[str]) -> int:
    text_lower = text.lower()
    return sum(1 for kw in keywords if kw.lower() in text_lower)


def _check_header_patterns(text: str) -> list[str]:
    """Retorna padrões de cabeçalho encontrados."""
    found = []
    for pat in HEADER_PATTERNS:
        if pat.search(text):
            found.append(pat.pattern)
    return found


def _check_suspicious_patterns(text: str) -> list[str]:
    """Retorna padrões suspeitos encontrados no texto."""
    found = []
    for pat in SUSPICIOUS_PATTERNS:
        if pat.search(text):
            found.append(pat.pattern)
    return found


def run(file_path: Path, config: Optional[dict] = None) -> AuditResult:
    """
    Executa verificação OCR e análise de conteúdo do PDF.

    Args:
        file_path: Caminho do arquivo PDF.
        config: Configurações opcionais.

    Returns:
        AuditResult com análise de conteúdo.
    """
    log.info("skill.ocr.start", file=file_path.name)

    # 1. Tentativa de extração nativa
    text = _extract_text_native(file_path)
    extraction_method = "native_pdf"

    # 2. Fallback para OCR se texto insuficiente
    if len(text) < 200:
        log.info("skill.ocr.fallback_to_tesseract", file=file_path.name, text_len=len(text))
        text = _extract_text_ocr(file_path)
        extraction_method = "tesseract_ocr"

    if not text:
        return AuditResult(
            skill="ocr_verify",
            status=SkillStatus.ERROR,
            score=0.0,
            detail="Não foi possível extrair texto do PDF (nem nativo nem OCR).",
            evidence={"extraction_method": extraction_method, "text_length": 0},
            timestamp=datetime.utcnow().isoformat(),
        )

    log.info("skill.ocr.text_extracted", length=len(text), method=extraction_method)

    alerts = []
    scores = []
    evidence: dict = {
        "extraction_method": extraction_method,
        "text_length": len(text),
        "text_preview": text[:500].replace("\n", " "),
    }

    # ── Verificar palavras-chave obrigatórias ────────────
    required_found = _count_keywords(text, REQUIRED_KEYWORDS)
    required_total = len(REQUIRED_KEYWORDS)
    required_ratio = required_found / required_total

    evidence["required_keywords_found"] = required_found
    evidence["required_keywords_total"] = required_total

    if required_ratio >= 0.6:
        scores.append(0.9)
    elif required_ratio >= 0.3:
        scores.append(0.5)
        alerts.append(f"⚠️ Apenas {required_found}/{required_total} palavras-chave obrigatórias encontradas.")
    else:
        scores.append(0.0)
        alerts.append(f"🚨 CRÍTICO: Apenas {required_found}/{required_total} palavras obrigatórias. Documento pode não ser um Diário Oficial.")

    # ── Verificar padrões de cabeçalho ──────────────────
    header_found = _check_header_patterns(text)
    evidence["header_patterns_found"] = len(header_found)

    if len(header_found) >= 2:
        scores.append(0.9)
    elif len(header_found) == 1:
        scores.append(0.6)
        alerts.append("⚠️ Apenas 1 padrão de cabeçalho oficial detectado. Esperado: ≥ 2.")
    else:
        scores.append(0.1)
        alerts.append("🚨 CRÍTICO: Nenhum padrão de cabeçalho oficial detectado (ex: 'Diário Oficial', 'Ano X – Nº Y').")

    # ── Verificar palavras de reforço ───────────────────
    reinforcing_count = _count_keywords(text, REINFORCING_KEYWORDS)
    evidence["reinforcing_keywords_found"] = reinforcing_count

    if reinforcing_count >= 3:
        scores.append(0.8)
    elif reinforcing_count >= 1:
        scores.append(0.6)
    else:
        scores.append(0.3)
        alerts.append("⚠️ Nenhuma palavra de reforço encontrada (portaria, decreto, edital, etc.).")

    # ── Verificar padrões suspeitos no texto ────────────
    suspicious_found = _check_suspicious_patterns(text)
    evidence["suspicious_patterns"] = suspicious_found

    if suspicious_found:
        scores.append(0.0)
        alerts.append(f"🚨 Padrões suspeitos no texto: {suspicious_found}")
    else:
        scores.append(1.0)

    # ── Score final e veredito ─────────────────────────
    final_score = sum(scores) / len(scores)

    if final_score >= 0.75:
        status = SkillStatus.APPROVED
        detail = f"Conteúdo consistente com Diário Oficial. Keywords: {required_found}/{required_total}. Headers: {len(header_found)}."
    elif final_score >= 0.45:
        status = SkillStatus.CAUTION
        detail = " | ".join(alerts) if alerts else "Documento com inconsistências leves."
    else:
        status = SkillStatus.SUSPECT
        detail = "🚨 FRAUDE DETECTADA: " + " | ".join(alerts)

    return AuditResult(
        skill="ocr_verify",
        status=status,
        score=round(final_score, 3),
        detail=detail,
        evidence=evidence,
        timestamp=datetime.utcnow().isoformat(),
    )
