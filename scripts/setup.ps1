#!/usr/bin/env powershell
# OstraClaw — Setup Inicial (Windows PowerShell)
# Execute: .\scripts\setup.ps1

Write-Host "🦞 OstraClaw — Setup Inicial" -ForegroundColor Cyan
Write-Host "Guardião da Integridade Digital — PMRO`n" -ForegroundColor DarkCyan

# 1. Criar .env se não existir
if (-not (Test-Path ".\.env")) {
    Copy-Item ".\.env.example" ".\.env"
    Write-Host "✅ .env criado a partir do .env.example" -ForegroundColor Green
    Write-Host "⚠️  IMPORTANTE: Edite o .env com suas credenciais antes de continuar!" -ForegroundColor Yellow
} else {
    Write-Host "ℹ️  .env já existe" -ForegroundColor Blue
}

# 2. Criar estrutura de pastas de dados
$dirs = @(
    "data\raw",
    "data\quarantine",
    "data\processed",
    "data\reports",
    "logs"
)
foreach ($d in $dirs) {
    New-Item -ItemType Directory -Force -Path $d | Out-Null
}
Write-Host "✅ Estrutura de pastas criada" -ForegroundColor Green

# 3. Gerar PDF falso de teste
Write-Host "`n📄 Gerando PDF de teste (falso)..." -ForegroundColor Magenta
python scripts\generate_fake_jornal.py

# 4. Build e subida dos containers
Write-Host "`n🐳 Iniciando containers Docker..." -ForegroundColor Cyan
docker compose up -d --build

Write-Host "`n✅ OstraClaw está rodando!" -ForegroundColor Green
Write-Host "Dashboard: http://localhost:8501" -ForegroundColor Cyan
Write-Host "Logs:      docker logs -f ostraclaw_core`n" -ForegroundColor DarkGray

Write-Host "📥 Para auditar um jornal, copie o PDF para: .\data\raw\" -ForegroundColor Yellow
