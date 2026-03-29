"""
OstraClaw — Notifier
Dispara alertas via Telegram e Slack conforme o veredito.
"""
from __future__ import annotations

import os
from typing import Optional

import httpx
import structlog

log = structlog.get_logger(__name__)


def _truncate(text: str, length: int = 300) -> str:
    return text[:length] + "..." if len(text) > length else text


class Notifier:
    """Gerencia notificações para Telegram e Slack."""

    def __init__(self):
        self.telegram_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
        self.slack_webhook = os.getenv("SLACK_WEBHOOK_URL", "")

    async def send_fraud_alert(self, report: dict) -> None:
        """Alerta crítico — documento fraudulento detectado."""
        msg = (
            f"🚨 *FRAUDE DETECTADA — OstraClaw*\n\n"
            f"📄 *Arquivo:* `{report['file']}`\n"
            f"🔍 *Score:* {report['aggregate_score']:.2%}\n"
            f"❌ *Veredito:* FRAUD\n"
            f"📌 *Motivo:* {_truncate(report.get('main_reason', ''))}\n"
            f"⚠️ *Ação:* Arquivo movido para QUARENTENA."
        )
        await self._send_telegram(msg, parse_mode="Markdown")
        await self._send_slack({
            "text": "🚨 FRAUDE DETECTADA — OstraClaw",
            "attachments": [{
                "color": "#FF0000",
                "fields": [
                    {"title": "Arquivo", "value": report["file"], "short": True},
                    {"title": "Score", "value": f"{report['aggregate_score']:.2%}", "short": True},
                    {"title": "Motivo", "value": _truncate(report.get("main_reason", "")), "short": False},
                ],
            }],
        })

    async def send_caution_alert(self, report: dict) -> None:
        """Alerta de cautela — documento suspeito."""
        msg = (
            f"⚠️ *DOCUMENTO SUSPEITO — OstraClaw*\n\n"
            f"📄 *Arquivo:* `{report['file']}`\n"
            f"🔍 *Score:* {report['aggregate_score']:.2%}\n"
            f"❓ *Veredito:* SUSPECT\n"
            f"📌 *Motivo:* {_truncate(report.get('main_reason', ''))}\n"
            f"⚠️ *Ação:* Cópia enviada para quarentena. Revisão humana recomendada."
        )
        await self._send_telegram(msg, parse_mode="Markdown")

    async def _send_telegram(self, text: str, parse_mode: str = "Markdown") -> None:
        if not self.telegram_token or not self.telegram_chat_id:
            log.debug("notifier.telegram_not_configured")
            return
        try:
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json={
                    "chat_id": self.telegram_chat_id,
                    "text": text,
                    "parse_mode": parse_mode,
                })
                resp.raise_for_status()
                log.info("notifier.telegram_sent")
        except Exception as e:
            log.error("notifier.telegram_error", error=str(e))

    async def _send_slack(self, payload: dict) -> None:
        if not self.slack_webhook:
            log.debug("notifier.slack_not_configured")
            return
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(self.slack_webhook, json=payload)
                resp.raise_for_status()
                log.info("notifier.slack_sent")
        except Exception as e:
            log.error("notifier.slack_error", error=str(e))
