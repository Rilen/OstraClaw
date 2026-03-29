"""
OstraClaw — Agente Principal (main.py)
Guardião da Integridade Digital — PMRO

v1.7: Correção Crítica de Concorrência (Lock assíncrono), Tolerância a Falhas e Sensibilidade Ajustada.
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
import time
import logging
import traceback
from datetime import datetime
from pathlib import Path
from logging.handlers import RotatingFileHandler

import structlog
from rich.console import Console
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

# ── Caminhos ────────────────────────────────────────────────
INPUT_DIR = Path(os.getenv("INPUT_DIR", "/app/input_jornais"))
QUARANTINE_DIR = Path(os.getenv("QUARANTINE_DIR", "/app/quarantine"))
PROCESSED_DIR = Path(os.getenv("PROCESSED_DIR", "/app/processed"))
REPORTS_DIR = Path(os.getenv("REPORTS_DIR", "/app/reports"))
LOGS_DIR = Path(os.getenv("LOGS_DIR", "/app/logs"))

for d in [INPUT_DIR, QUARANTINE_DIR, PROCESSED_DIR, REPORTS_DIR, LOGS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ── Configuração de Logging ─────────────────────────────────
audit_log_file = LOGS_DIR / "audit.log"
file_handler = RotatingFileHandler(audit_log_file, maxBytes=5*1024*1024, backupCount=2)
file_handler.setFormatter(logging.Formatter('%(message)s'))

logging.basicConfig(level=logging.INFO, handlers=[file_handler, logging.StreamHandler()])

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S", utc=False),
        structlog.processors.JSONRenderer(),
    ],
    logger_factory=structlog.PrintLoggerFactory(file=open(audit_log_file, "a")),
)
log = structlog.get_logger("ostraclaw.core")
console = Console()

# ── Importar componentes ────────────────────────────────────
sys.path.insert(0, "/app")
from skills import AuditResult, SkillStatus, skill_hash_check, skill_metadata_extractor, skill_ocr_verify
from agent.llm_client import LLMClient
from agent.notifier import Notifier
from agent.db import Database
from agent.reporter import ReportWriter

SYSTEM_PROMPT = """Você é o OstraClaw, auditor forense de documentos da PMRO.
Analise os resultados das skills (Hash, Metadados, OCR) e emita o veredito final.
REGRAS:
- Metadados ausentes não significam FRAUD, mas sim SUSPECT ou AUTHENTIC dependendo do restante.
- OCR sem palavras-chave municipais (Rio das Ostras, Gabinete) indica SUSPECT.
- Hash divergente de oficial é FRAUD.

Responda em JSON: { "veredito": "AUTHENTIC|SUSPECT|FRAUD", "confianca": 0.0-1.0, "motivo_principal": "X", "evidencias": [] }"""

class JornalAuditor:
    def __init__(self):
        self.db = Database()
        self.llm = LLMClient(system_prompt=SYSTEM_PROMPT)
        self.notifier = Notifier()
        self.reporter = ReportWriter(REPORTS_DIR)
        self.known_hashes = self.db.get_official_hashes()
        self._lock = asyncio.Lock() # Impede que dois arquivos atropelem o LLM e causem travamento

    async def audit(self, file_path: Path):
        async with self._lock:
            try:
                await self._process_file(file_path)
            except Exception as e:
                log.error("audit.failed", file=file_path.name, error=str(e), trace=traceback.format_exc())
                # Em caso de falha crítica (arquivo corrompido, etc), colocar em quarentena
                try:
                    dest = QUARANTINE_DIR / f"ERROR_{file_path.name}"
                    shutil.move(file_path, dest)
                except: pass

    async def _process_file(self, file_path: Path) -> dict:
        log.info("audit.start", file=file_path.name)
        start_time = time.time()
        results: list[AuditResult] = []
        
        # Skill 1/4: Hash
        log.info("progress", step=1, total=4, phase="Integridade Hash", file=file_path.name)
        results.append(skill_hash_check.run(file_path, self.known_hashes))

        # Skill 2/4: Metadados
        log.info("progress", step=2, total=4, phase="Análise de Metadados", file=file_path.name)
        results.append(skill_metadata_extractor.run(file_path))

        # Skill 3/4: OCR
        log.info("progress", step=3, total=4, phase="Extração OCR", file=file_path.name)
        results.append(skill_ocr_verify.run(file_path))

        # Skill 4/4: LLM
        log.info("progress", step=4, total=4, phase="Análise via Llama 3.2", file=file_path.name)
        
        avg_score = sum(r.score for r in results) / len(results)
        
        preliminary = "AUTHENTIC"
        if any(r.status == SkillStatus.SUSPECT for r in results) or avg_score < 0.7:
             preliminary = "SUSPECT"
        if any(r.is_critical for r in results) or avg_score < 0.35:
             preliminary = "FRAUD"
        
        llm_verdict = await self.llm.analyze(results, preliminary, file_path.name)
        final_verdict = llm_verdict.get("veredito", preliminary)
        duration = time.time() - start_time

        report = {
            "file": file_path.name,
            "timestamp": datetime.now().isoformat(),
            "aggregate_score": round(avg_score, 3),
            "preliminary_verdict": preliminary,
            "final_verdict": final_verdict,
            "confidence": llm_verdict.get("confianca", avg_score),
            "main_reason": llm_verdict.get("motivo_principal", "Análise inconclusiva"),
            "evidencias": llm_verdict.get("evidencias", []),
            "skill_results": [r.model_dump() for r in results],
            "duration_seconds": round(duration, 2)
        }

        # Persistir
        try:
            self.reporter.write(report)
            self.db.save_audit(report)
            log.info("audit.finish", file=file_path.name, verdict=final_verdict)
        except Exception as e:
            log.error("audit.save_failed", file=file_path.name, error=str(e))

        # Ação Física
        await self._execute_verdict(file_path, report)
        return report

    async def _execute_verdict(self, file_path: Path, report: dict):
        v = report["final_verdict"]
        if v == "FRAUD":
            shutil.move(file_path, QUARANTINE_DIR / file_path.name)
            try: await self.notifier.send_fraud_alert(report)
            except: pass
        elif v == "SUSPECT":
            shutil.move(file_path, QUARANTINE_DIR / f"SUS_REV_{file_path.name}")
        else:
            shutil.move(file_path, PROCESSED_DIR / file_path.name)

class PDFWatcher(FileSystemEventHandler):
    def __init__(self, auditor, loop):
        self.auditor = auditor
        self.loop = loop
    def on_created(self, event):
        if not event.is_directory and event.src_path.lower().endswith(".pdf"):
            time.sleep(1.5) # Aguardar sistema operacional liberar o arquivo copiado
            asyncio.run_coroutine_threadsafe(self.auditor.audit(Path(event.src_path)), self.loop)

async def main():
    auditor = JornalAuditor()
    loop = asyncio.get_running_loop()
    
    # Processar os que já existirem na pasta de forma enfileirada
    for pdf in sorted(INPUT_DIR.glob("*.pdf")):
        await auditor.audit(pdf)

    # Iniciar Monitoramento
    observer = Observer()
    observer.schedule(PDFWatcher(auditor, loop), str(INPUT_DIR), recursive=False)
    observer.start()
    
    log.info("ostraclaw.ready", monitoring=str(INPUT_DIR))
    try:
        while True: await asyncio.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        log.info("ostraclaw.shutdown")
    observer.join()

if __name__ == "__main__":
    asyncio.run(main())
