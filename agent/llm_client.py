"""
OstraClaw — LLM Client
Cliente para Ollama (LLM local). Analisa resultados das skills
e produz um parecer técnico fundamentado.
"""
from __future__ import annotations

import json
import re
from typing import Any, Optional

import httpx
import structlog

log = structlog.get_logger(__name__)

# Defaults
DEFAULT_OLLAMA_URL = "http://ollama:11434"
DEFAULT_MODEL = "llama3.2:3b"


def _parse_json_response(text: str) -> dict:
    """Extrai JSON da resposta do LLM (que pode ter texto ao redor)."""
    # Tenta parse direto
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    # Busca bloco JSON no texto
    match = re.search(r"\{[\s\S]+\}", text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    log.warning("llm.parse_failed", raw=text[:300])
    return {}


class LLMClient:
    """Cliente Ollama para análise de parecer de auditoria."""

    def __init__(
        self,
        system_prompt: str,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ):
        import os
        self.system_prompt = system_prompt
        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_URL)
        self.model = model or os.getenv("OLLAMA_MODEL", DEFAULT_MODEL)
        self._client = httpx.AsyncClient(timeout=120.0, base_url=self.base_url)

    def _build_user_prompt(self, results: list, preliminary_verdict: str, filename: str) -> str:
        """Monta o prompt com os resultados das skills."""
        lines = [
            f"ARQUIVO: {filename}",
            f"VEREDITO PRELIMINAR: {preliminary_verdict}",
            "\nRESULTADOS DAS SKILLS DE AUDITORIA:",
        ]
        for r in results:
            lines.append(f"\n=== {r.skill.upper()} ===")
            lines.append(f"Status: {r.status.value}")
            lines.append(f"Score: {r.score:.2%}")
            lines.append(f"Detalhe: {r.detail}")
            if r.evidence:
                lines.append(f"Evidências: {json.dumps(r.evidence, ensure_ascii=False, indent=2)[:600]}")

        lines.append("\nEmita seu parecer técnico no formato JSON solicitado.")
        return "\n".join(lines)

    async def analyze(self, results: list, preliminary_verdict: str, filename: str) -> dict:
        """
        Envia análise ao Ollama e retorna o veredito estruturado.
        Caso o Ollama falhe, usa o veredito preliminar (fallback).
        """
        user_prompt = self._build_user_prompt(results, preliminary_verdict, filename)

        try:
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "stream": False,
                "format": "json",  # Força Ollama a responder em JSON
                "options": {
                    "temperature": 0.1,   # Baixa criatividade — queremos consistência
                    "num_predict": 512,
                },
            }

            response = await self._client.post("/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()
            content = data.get("message", {}).get("content", "")
            parsed = _parse_json_response(content)

            if parsed.get("veredito"):
                log.info("llm.analyzed", verdict=parsed["veredito"], file=filename)
                return parsed

        except httpx.ConnectError:
            log.warning("llm.ollama_unavailable", fallback=preliminary_verdict)
        except httpx.HTTPStatusError as e:
            log.error("llm.http_error", status=e.response.status_code)
        except Exception as e:
            log.error("llm.unexpected_error", error=str(e))

        # ── Fallback: veredito determinístico sem LLM ─────
        scores = [r.score for r in results]
        avg_score = sum(scores) / len(scores) if scores else 0.5
        suspects = [r.detail for r in results if r.status.value in ("SUSPECT", "CAUTION")]

        return {
            "veredito": preliminary_verdict,
            "confianca": round(avg_score, 3),
            "motivo_principal": suspects[0] if suspects else "Análise automática (Ollama indisponível)",
            "evidencias": suspects,
            "acao_recomendada": (
                "Mover para quarentena e aguardar revisão humana."
                if preliminary_verdict != "AUTHENTIC"
                else "Ingerir no OstraIA."
            ),
        }

    async def close(self):
        await self._client.aclose()
