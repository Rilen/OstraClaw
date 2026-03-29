# 🦞 OstraClaw (OpenSource OpenClaw) — O Guardião da Integridade Digital

> **Projeto:** Sistema autônomo open-source de auditoria e detecção de fraudes em documentos governamentais (focado inicialmente na PMRO).  
> **Versão:** 1.7.0 (Stable release)  
> **Status:** MVP Avançado — Produção Ready

---

## 🎯 O que é o OpenClaw?

O OpenClaw é um **Agente Autônomo Forense**. Ele monitora sistemas de arquivos em busca de publicações governamentais (Jornais Oficiais, Leis, Decretos) em formato PDF e executa um rigoroso **pipeline de 4 camadas de auditoria** para atestar a veracidade do arquivo antes que ele seja ingerido por plataformas de IA ou disponibilizado ao público. Todo o cérebro do Agente roda **100% offline** através de um LLM local, garantindo máxima privacidade (Privacy-first).

```text
Upload PDF → [Fila Assíncrona] → [Hash] → [Metadados] → [OCR Forense] → [LLM Ollama] → Veredito
                                                                                          ↓
                                                                   AUTHENTIC (Seguro) → /processed
                                                                   SUSPECT (Duvidoso) → /quarantine
                                                                   FRAUD (Adulterado) → /quarantine + Alertas
```

---

## ✨ Novidades da Versão 1.7.0 

- **Fila de Processamento Resiliente (Locks Assíncronos):** Agora o sistema suporta o envio de dezenas de arquivos simultâneos. O Agente organiza tudo em fila, garantindo que o LLM local não sofra gargalos ou trave.
- **Tolerância a Falhas Críticas:** Arquivos corrompidos não derrubam mais o Agente. Eles são isolados com a tag `ERROR_` e o fluxo continua perfeitamente.
- **Dashboard de Investigação Premium:** Uma interface Streamlit completamente reformulada.
  * *Monitoramento em Tempo Real:* Acompanhe em qual etapa da auditoria (1 a 4) o arquivo está, no exato segundo.
  * *Laudo Técnico Inteligente:* Exibição da justificativa da IA (Llama 3.2), evidências coletadas e o resultado unitário de cada Skill.
  * *UX/UI Governamental:* Botões de envio inteligentes com anti-spam e layout corporativo focado em acessibilidade.
- **Sensibilidade Calibrada:** O Agente entende o contexto de criação em órgãos públicos (ausência de metadados simples) e evita falsos positivos.

---

## 🏗️ Arquitetura

O sistema é montado em arquitetura de **Microserviços via Docker**:

1. **`ostraclaw_core`:** O "Motor". Roda o script de Python com o Watchdog, executando as auditorias em fila.
2. **`ostraclaw_dashboard`:** A "Janela". Aplicação Streamlit na porta 8501.
3. **`ostraclaw_db`:** A "Memória". Banco PostgreSQL persistente para gravar o histórico de auditoria contra adulterações.
4. **`ollama (Llama 3.2)`:** O "Cérebro". Inteligência artificial local responsável por dar o Veredito Forense com base nos relatórios técnicos.

---

## 🚀 Como Executar (Quick Start)

### 1. Pré-requisitos
- Docker Desktop rodando.
- Windows PowerShell (ou terminal similar linux via `sh`).

### 2. Subir o Ecossistema
```powershell
# Clone o repositório
git clone https://github.com/seu-usuario/OpenClaw.git
cd OpenClaw

# Inicialize os containers de forma limpa
docker compose up -d --build

# Acesse o Dashboard e comece a testar
http://localhost:8501 
```

---

## ⚙️ Skills de Auditoria (O Pipeline)

| Fases de Voo | Skill | O que ela descobre |
|--------------|-------|--------------------|
| **1/4** | `skill_hash_check` | Compara a assinatura binária do arquivo (SHA-256) contra as assinaturas originais salvas no Banco de Dados. |
| **2/4** | `skill_metadata_extractor` | Vasculha o código do PDF buscando traços de edição clandestina (e.g., Photoshop, Canva, PDFEdit) e adulteração temporal. |
| **3/4** | `skill_ocr_verify` | Extrai visualmente o texto e valida marcas d'água de texto esperadas (Prefeitura, Edição, Diário Oficial). |
| **4/4** | **`LLM Analysis`** | O Llama 3.2 consome o resultado das 3 skills acima, raciocina sobre os possíveis motivos e decreta o Parecer Técnico. |

---

## 🔭 Próximos Passos (Roadmap)
- [ ] **Visão Computacional:** Adicionar a `Skill_Visual_Check` para detectar brasões adulterados visualmente.
- [ ] **Webhook API:** Permitir que microsserviços batam em uma API RESTful do OpenClaw para liberação de arquivos sistêmicos.
- [ ] **Multi-Modelos:** Parametrizar a escolha do LLM via ambiente (podendo plugar Qwen, Mistral, ou Phi-3).

---
*OpenClaw v1.7.0 — Open Source Civic-Tech © 2026*
