"""
OstraClaw — Dashboard v1.7.0 (INVESTIGATIVE DASHBOARD)
Adicionado: Detalhes forenses por Skill e UX Analítica Premium.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text

st.set_page_config(
    page_title="OstraClaw — Dashboard de Integridade",
    page_icon="🦞",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Estilo Premium ──────
st.markdown("""
<style>
[data-testid="stAppViewContainer"] { background-color: #F8FAFC !important; }
[data-testid="stSidebar"] { background-color: #FFFFFF !important; border-right: 1px solid #E2E8F0; }
h1, h2, h3 { color: #1E293B !important; font-weight: 700; }
.metric-card {
    background: #FFF; border: 1px solid #E2E8F0; border-radius: 12px;
    padding: 1.2rem; text-align: center; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
}
.metric-value { font-size: 2.2rem; font-weight: 800; color: #0F172A; }
.status-monitor {
    background: linear-gradient(135deg, #0284C7, #0369A1); color: white;
    border-radius: 12px; padding: 2rem; margin-bottom: 2rem;
    box-shadow: 0 10px 15px -3px rgba(0, 132, 199, 0.3);
}
.skill-box {
    background: white; border: 1px solid #E2E8F0; border-radius: 10px;
    padding: 1rem; margin-bottom: 10px; border-left: 5px solid #CBD5E1;
}
.skill-box.pass { border-left-color: #22C55E; }
.skill-box.fail { border-left-color: #EF4444; }
.skill-box.warn { border-left-color: #F59E0B; }
</style>
""", unsafe_allow_html=True)

REPORTS_DIR = Path(os.getenv("REPORTS_DIR", "/app/reports"))
INPUT_DIR = Path(os.getenv("INPUT_DIR", "/app/input_jornais"))
LOG_FILE = Path(os.getenv("LOG_FILE", "/app/logs/audit.log"))

@st.cache_data(ttl=1)
def load_reports() -> list[dict]:
    reports = []
    if not REPORTS_DIR.exists(): return []
    for f in sorted(REPORTS_DIR.glob("*.json"), reverse=True):
        try: reports.append(json.loads(f.read_text(encoding="utf-8")))
        except: pass
    return reports

def get_latest_status():
    if not LOG_FILE.exists(): return None
    try:
        lines = LOG_FILE.read_text().splitlines()
        for i in range(len(lines)-1, -1, -1):
            line = lines[i]
            try:
                data = json.loads(line)
                if data.get("event") in ["progress", "audit.start"]: return data
                if data.get("event") == "audit.finish": return None
            except: pass
    except: pass
    return None

def get_all_logs(limit=10):
    """Lê as últimas linhas do log para a sidebar."""
    if not LOG_FILE.exists(): return []
    try:
        lines = LOG_FILE.read_text().splitlines()
        logs = []
        for line in reversed(lines[-limit:]):
            try:
                data = json.loads(line)
                phase = data.get("phase", data.get("event",""))
                logs.append({"time": data.get("timestamp","").split(" ")[-1], "event": phase})
            except: logs.append({"time": "-", "event": "raw"})
        return logs
    except: return []

# Status global para saber se devemos bloquear o botão
is_processing = get_latest_status() is not None

# ── Sidebar ──
with st.sidebar:
    st.markdown("<h1 style='text-align: center;'>🦞 OstraClaw</h1>", unsafe_allow_html=True)
    st.divider()
    
    with st.form("upload_form", clear_on_submit=True):
        files = st.file_uploader("Upload de Jornais:", type=["pdf"], accept_multiple_files=True, disabled=is_processing)
        
        btn_label = "⏳ AUDITORIA EM ANDAMENTO..." if is_processing else "🚀 INICIAR AUDITORIA"
        if st.form_submit_button(btn_label, use_container_width=True, type="primary", disabled=is_processing):
            if files:
                for f in files:
                    with open(INPUT_DIR / f.name, "wb") as out: out.write(f.getvalue())
                st.toast(f"Enviado {len(files)} arquivos.")
                time.sleep(1)
                st.rerun()

    # Log na sidebar restaurado
    with st.expander("🎞 Log Técnico", expanded=True):
        logs = get_all_logs()
        if not logs:
            st.caption("Sem atividades recentes.")
        else:
            for l in logs:
                st.caption(f"**{l['time']}** | _ {l['event']} _")

    st.divider()
    if st.button("🗑️ LIMPAR HISTÓRICO", use_container_width=True, disabled=is_processing):
        for f in REPORTS_DIR.glob("*.*"): f.unlink()
        if LOG_FILE.exists(): LOG_FILE.write_text("")
        st.rerun()

# ── Main ──
st.title("🛡️ Central de Auditoria Governamental")

# Monitor de Progresso
status = get_latest_status()
if status:
    st.markdown(f"""
    <div class="status-monitor">
        <h3 style="margin:0; color:white;">⏳ Processamento Ativo</h3>
        <p style="font-size:1.3rem; margin-top:10px;"><b>{status.get('phase','Analisando')}</b> ({status.get('step',0)}/4)</p>
        <p style="opacity:0.8">📄 <i>{status.get('file','Salvando...')}</i></p>
    </div>
    """, unsafe_allow_html=True)
    st.progress(status.get("step", 0) / 4)
    time.sleep(2)
    st.rerun()

reports = load_reports()
if not reports:
    st.info("📦 **Sistema pronto para Auditoria.** Use o painel lateral para enviar documentos.")
    st.stop()

df = pd.DataFrame(reports)

# Top KPIs
c1, c2, c3, c4 = st.columns(4)
c1.markdown(f"<div class='metric-card'><div class='metric-label'>Processados</div><div class='metric-value'>{len(df)}</div></div>", unsafe_allow_html=True)
c2.markdown(f"<div class='metric-card'><div class='metric-label'>Autênticos</div><div class='metric-value' style='color:#22C55E'>{(df['final_verdict'] == 'AUTHENTIC').sum()}</div></div>", unsafe_allow_html=True)
c3.markdown(f"<div class='metric-card'><div class='metric-label'>Suspeitos</div><div class='metric-value' style='color:#F59E0B'>{(df['final_verdict'] == 'SUSPECT').sum()}</div></div>", unsafe_allow_html=True)
c4.markdown(f"<div class='metric-card'><div class='metric-label'>Fraudes</div><div class='metric-value' style='color:#EF4444'>{(df['final_verdict'] == 'FRAUD').sum()}</div></div>", unsafe_allow_html=True)

st.divider()

# Tabela Minimalista
st.subheader("📊 Filtro Operacional")
search = st.text_input("🔍 Buscar por nome do arquivo...", "")
filt_df = df[df["file"].str.contains(search, case=False)] if search else df
st.dataframe(filt_df[["file", "timestamp", "final_verdict", "aggregate_score"]], use_container_width=True, hide_index=True)

st.divider()

# --- DASHBOARD DE ANÁLISE DETALHADA ---
st.subheader("🔍 Painel de Investigação Forense")
selected_file = st.selectbox("Selecione o arquivo para o Laudo Técnico:", df["file"].tolist())

if selected_file:
    rep = next(r for r in reports if r["file"] == selected_file)
    
    # ── Header de Laudo ──
    v = rep["final_verdict"]
    color = "#22C55E" if v == "AUTHENTIC" else "#F59E0B" if v == "SUSPECT" else "#EF4444"
    st.markdown(f"""
        <div style="padding:1rem; border-radius:10px; background:{color}10; border:2px solid {color}; margin-bottom:20px;">
            <h2 style="margin:0; color:{color};">Veredito Final: {v}</h2>
            <p style="margin:0; font-weight:bold; color:#1E293B">Score de Confiança: {rep['confidence']:.2%}</p>
        </div>
    """, unsafe_allow_html=True)
    
    col_a, col_b = st.columns([1, 2])
    
    with col_a:
        st.write("##### 🧬 Resultado das Skills")
        for s in rep.get("skill_results", []):
            sk_name = s['skill'].replace('_', ' ').title()
            sk_status = s['status']
            css_cls = "pass" if sk_status == "APPROVED" else "fail" if sk_status == "SUSPECT" else "warn"
            icon = "✅" if sk_status == "APPROVED" else "🚨" if sk_status == "SUSPECT" else "⚠️"
            
            st.markdown(f"""
                <div class="skill-box {css_cls}">
                    <div style="font-size:0.8rem; color:#64748B">{sk_name}</div>
                    <div style="font-weight:bold;">{icon} {sk_status}</div>
                    <div style="font-size:0.75rem; color:#475569">{s.get('detail','-')}</div>
                </div>
            """, unsafe_allow_html=True)

    with col_b:
        st.write("##### 🧠 Parecer da IA (Llama 3.2)")
        st.info(f"**Motivo Principal:**\n\n{rep.get('main_reason', 'Nenhuma justificativa técnica fornecida.')}")
        
        if rep.get("evidencias"):
            st.write("**📍 Evidências Encontradas:**")
            for e in rep["evidencias"]:
                st.markdown(f"- {e}")
                
        with st.expander("🛠️ Ver Metadados Brutos"):
            valid_skill = next((s for s in rep["skill_results"] if s["skill"] == "metadata_extractor"), None)
            if valid_skill: st.json(valid_skill.get("evidence", {}))
