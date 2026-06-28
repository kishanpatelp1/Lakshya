# Local LLM Setup (DeepSeek-V3 + Ollama)

## Requirements

- **DeepSeek-V3**: ~170–404GB disk, 24–48GB VRAM (or CPU+swap with slower inference)
- **nomic-embed-text**: ~274MB
- **Ollama**: v0.5.5+ for DeepSeek-V3

## Quick Start (Windows)

```powershell
# Run the setup script from repository root
.\backend-ai\scripts\download_models.ps1
```

## Location

All backend operational scripts are located in `backend-ai/scripts/`.

Common commands from repository root:

```bash
python backend-ai/scripts/seed_db.py
python backend-ai/scripts/run_agent.py
python backend-ai/scripts/debug_run.py
python backend-ai/scripts/test_imports.py
```

## Manual Steps

### 1. Install Ollama

1. Download: https://ollama.com/download
2. Run the installer and complete setup
3. Ollama runs as a background service (API at http://localhost:11434)

### 2. Pull Models

```powershell
# LLM (choose one)
ollama pull deepseek-v3      # Full model (~404GB)
ollama pull deepseek-v3:8b   # Smaller quantized if available
ollama pull deepseek-r1:7b   # Smaller alternative

# Embeddings (required for vector search)
ollama pull nomic-embed-text
```

### 3. Configure .env

Copy `.env.example` to `.env` and ensure:

```
LLM_PROVIDER=ollama
LLM_MODEL=deepseek-v3
OLLAMA_BASE_URL=http://localhost:11434
EMBEDDING_PROVIDER=ollama
EMBEDDING_MODEL=nomic-embed-text
EMBEDDING_DIM=768
```

### 4. Qdrant Collection Size

If using `nomic-embed-text`, embeddings are **768** dimensions (not 1536). Ensure Qdrant collections are created with `size=768`.

## Alternative: DeepSeek API (Cloud)

To use DeepSeek API instead of local:

```
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=sk-...
LLM_MODEL=deepseek-chat
```

## Alternative: OpenAI

```
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIM=1536
```
