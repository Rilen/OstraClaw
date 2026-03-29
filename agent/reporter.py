"""
OstraClaw — Report Writer
Gera relatórios JSON + HTML de cada auditoria.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

import structlog
from jinja2 import Environment, BaseLoader

log = structlog.get_logger(__name__)

# Template HTML do relatório
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>OstraClaw — Relatório: {{ report.file }}</title>
<style>
  body { font-family: 'Segoe UI', sans-serif; background: #0d1117; color: #e6edf3; margin: 0; padding: 2rem; }
  .container { max-width: 900px; margin: 0 auto; }
  .header { display: flex; align-items: center; gap: 1rem; margin-bottom: 2rem; }
  .logo { font-size: 3rem; }
  h1 { font-size: 1.4rem; color: #58a6ff; margin: 0; }
  .subtitle { color: #8b949e; font-size: 0.9rem; }
  .verdict {
    padding: 1rem 2rem; border-radius: 12px; text-align: center; font-size: 1.5rem;
    font-weight: bold; margin-bottom: 2rem; letter-spacing: 2px;
  }
  .AUTHENTIC { background: #1a3a1a; border: 2px solid #3fb950; color: #3fb950; }
  .SUSPECT   { background: #3a2a0a; border: 2px solid #e3b341; color: #e3b341; }
  .FRAUD     { background: #3a0a0a; border: 2px solid #f85149; color: #f85149; }
  .card { background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 1.5rem; margin-bottom: 1rem; }
  .card h2 { color: #58a6ff; margin: 0 0 1rem 0; font-size: 1rem; text-transform: uppercase; letter-spacing: 1px; }
  .row { display: flex; gap: 1rem; margin-bottom: 0.5rem; }
  .label { color: #8b949e; width: 180px; flex-shrink: 0; }
  .value { color: #e6edf3; }
  .score-bar { background: #21262d; border-radius: 4px; height: 8px; margin-top: 4px; }
  .score-fill { height: 100%; border-radius: 4px; }
  .skill-card { background: #0d1117; border: 1px solid #21262d; border-radius: 8px; padding: 1rem; margin-bottom: 0.8rem; }
  .skill-name { font-weight: bold; color: #58a6ff; margin-bottom: 0.3rem; }
  .APPROVED { color: #3fb950 !important; } .SUSPECT { color: #f85149 !important; }
  .CAUTION  { color: #e3b341 !important; } .UNKNOWN { color: #8b949e !important; }
  .evidence { font-family: monospace; font-size: 0.75rem; color: #8b949e; white-space: pre-wrap; word-break: break-all; }
  .footer { color: #8b949e; font-size: 0.8rem; margin-top: 3rem; text-align: center; }
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <span class="logo">🦞</span>
    <div>
      <h1>OstraClaw — Relatório de Auditoria</h1>
      <div class="subtitle">Guardião da Integridade Digital — PMRO | {{ report.timestamp }}</div>
    </div>
  </div>

  <div class="verdict {{ report.final_verdict }}">
    {% if report.final_verdict == 'FRAUD' %}🚨 FRAUDE DETECTADA
    {% elif report.final_verdict == 'SUSPECT' %}⚠️ DOCUMENTO SUSPEITO
    {% else %}✅ AUTÊNTICO
    {% endif %}
  </div>

  <div class="card">
    <h2>📄 Identificação</h2>
    <div class="row"><span class="label">Arquivo:</span><span class="value">{{ report.file }}</span></div>
    <div class="row"><span class="label">Score Agregado:</span>
      <span class="value">
        {{ (report.aggregate_score * 100) | round(1) }}%
        <div class="score-bar">
          <div class="score-fill" style="width:{{ (report.aggregate_score * 100) | round(1) }}%;
            background: {% if report.aggregate_score >= 0.65 %}#3fb950{% elif report.aggregate_score >= 0.35 %}#e3b341{% else %}#f85149{% endif %}"></div>
        </div>
      </span>
    </div>
    <div class="row"><span class="label">Confiança LLM:</span><span class="value">{{ (report.confidence * 100) | round(1) }}%</span></div>
    <div class="row"><span class="label">Duração:</span><span class="value">{{ report.duration_seconds }}s</span></div>
    <div class="row"><span class="label">Motivo Principal:</span><span class="value">{{ report.main_reason }}</span></div>
  </div>

  {% if report.evidences %}
  <div class="card">
    <h2>🔍 Evidências Identificadas</h2>
    {% for ev in report.evidences %}
    <div class="row">• {{ ev }}</div>
    {% endfor %}
  </div>
  {% endif %}

  <div class="card">
    <h2>⚙️ Resultados das Skills</h2>
    {% for skill in report.skill_results %}
    <div class="skill-card">
      <div class="skill-name {{ skill.status }}">{{ skill.skill | upper }} — {{ skill.status }}</div>
      <div class="row"><span class="label">Score:</span><span class="value">{{ (skill.score * 100) | round(1) }}%</span></div>
      <div class="row"><span class="label">Detalhe:</span><span class="value">{{ skill.detail }}</span></div>
      {% if skill.evidence %}
      <details>
        <summary style="cursor:pointer; color:#58a6ff; margin-top:0.5rem;">Ver evidências brutas</summary>
        <pre class="evidence">{{ skill.evidence | tojson(indent=2) }}</pre>
      </details>
      {% endif %}
    </div>
    {% endfor %}
  </div>

  <div class="footer">OstraClaw v1.0 — Sistema de Auditoria Autônoma — PMRO © {{ report.timestamp[:4] }}</div>
</div>
</body>
</html>
"""


class ReportWriter:
    """Salva relatórios de auditoria em JSON e HTML."""

    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._env = Environment(loader=BaseLoader())
        self._env.filters["tojson"] = lambda v, **kw: json.dumps(v, ensure_ascii=False, **kw)
        self._template = self._env.from_string(HTML_TEMPLATE)

    def write(self, report: dict) -> None:
        """Salva relatório JSON e HTML."""
        stem = Path(report["file"]).stem
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        base_name = f"{stem}_{timestamp}"

        # JSON
        json_path = self.output_dir / f"{base_name}.json"
        json_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        # HTML
        html_path = self.output_dir / f"{base_name}.html"
        html_content = self._template.render(report=report)
        html_path.write_text(html_content, encoding="utf-8")

        log.info("reporter.saved", json=str(json_path), html=str(html_path))
