# ============================================================
#  OstraClaw — Dockerfile Principal
# ============================================================
FROM python:3.12-slim

# Dependências de sistema (Tesseract OCR, Poppler para PDFs)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-por \
    poppler-utils \
    libpq-dev \
    gcc \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instalar dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código do agente
COPY agent/ ./agent/
COPY skills/ ./skills/
COPY config/ ./config/

# Criar pastas de volume se não existirem
RUN mkdir -p /app/input_jornais /app/quarantine /app/processed /app/reports /app/logs

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import os; os.path.exists('/app/agent/main.py') or exit(1)"

CMD ["python", "-u", "agent/main.py"]
