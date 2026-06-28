# Download Ollama and pull DeepSeek-V3 + nomic-embed-text for local inference
# Run in PowerShell from repo root: .\backend-ai\scripts\download_models.ps1

$ErrorActionPreference = "Stop"

Write-Host "=== Lakshya - Local LLM Setup ===" -ForegroundColor Cyan
Write-Host ""

# 1. Check/install Ollama
$ollamaPath = Get-Command ollama -ErrorAction SilentlyContinue
if (-not $ollamaPath) {
    Write-Host "Ollama not found. Installing..." -ForegroundColor Yellow
    $installerUrl = "https://ollama.com/download/OllamaSetup.exe"
    $installerPath = "$env:TEMP\OllamaSetup.exe"

    try {
        Invoke-WebRequest -Uri $installerUrl -OutFile $installerPath -UseBasicParsing
        Write-Host "Running Ollama installer. Please complete the setup in the GUI." -ForegroundColor Yellow
        Start-Process -FilePath $installerPath -Wait
        Remove-Item $installerPath -ErrorAction SilentlyContinue
    } catch {
        Write-Host "ERROR: Could not download Ollama. Please install manually from: https://ollama.com/download" -ForegroundColor Red
        exit 1
    }

    Write-Host "Ollama installed. Restart this script after the installer finishes." -ForegroundColor Green
    exit 0
}

Write-Host "Ollama found. Checking if Ollama service is running..." -ForegroundColor Green
try {
    $null = Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -Method Get -TimeoutSec 3
    Write-Host "Ollama is running." -ForegroundColor Green
} catch {
    Write-Host "Starting Ollama (if installed but not running)..." -ForegroundColor Yellow
    Start-Process ollama -ArgumentList "serve" -WindowStyle Hidden
    Start-Sleep -Seconds 5
}

# 2. Pull DeepSeek-V3 (LLM)
Write-Host ""
Write-Host "Pulling DeepSeek-V3 (~404GB full / ~170GB quantized). This may take a while." -ForegroundColor Yellow
Write-Host "Alternative smaller models: deepseek-r1:7b, deepseek-coder-v2 (run: ollama pull <model>)" -ForegroundColor Gray

$pullDeepseek = Read-Host "Pull deepseek-v3? (y/n, default: y)"
if ($pullDeepseek -ne "n") {
    ollama pull deepseek-v3
    if ($LASTEXITCODE -ne 0) {
        Write-Host "DeepSeek-V3 pull failed. Try a smaller model: ollama pull deepseek-r1:7b" -ForegroundColor Red
    } else {
        Write-Host "DeepSeek-V3 ready." -ForegroundColor Green
    }
}

# 3. Pull nomic-embed-text (embeddings)
Write-Host ""
Write-Host "Pulling nomic-embed-text (~274MB) for vector search embeddings..." -ForegroundColor Yellow
ollama pull nomic-embed-text
if ($LASTEXITCODE -eq 0) {
    Write-Host "nomic-embed-text ready." -ForegroundColor Green
} else {
    Write-Host "nomic-embed-text pull failed." -ForegroundColor Red
}

Write-Host ""
Write-Host "=== Setup complete ===" -ForegroundColor Cyan
Write-Host "Ensure your .env has:" -ForegroundColor White
Write-Host "  LLM_PROVIDER=ollama" -ForegroundColor Gray
Write-Host "  LLM_MODEL=deepseek-v3" -ForegroundColor Gray
Write-Host "  OLLAMA_BASE_URL=http://localhost:11434" -ForegroundColor Gray
Write-Host "  EMBEDDING_PROVIDER=ollama" -ForegroundColor Gray
Write-Host "  EMBEDDING_MODEL=nomic-embed-text" -ForegroundColor Gray
Write-Host "  EMBEDDING_DIM=768" -ForegroundColor Gray
