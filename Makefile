# Lakshya — local dev supervisor
# Each long-running process gets its own target (run in separate terminals),
# plus one-shot helpers for infra and health.

BACKEND := backend-ai
PY      := $(BACKEND)/.venv/bin/python
CELERY  := $(BACKEND)/.venv/bin/celery

.PHONY: help infra infra-stop backend worker beat frontend eval health seed stop-all

help:
	@echo "Lakshya dev targets:"
	@echo "  make infra      - start Redis + Ollama (Homebrew services)"
	@echo "  make backend    - FastAPI API on :8001 (reload)"
	@echo "  make worker     - Celery worker (background jobs)"
	@echo "  make beat       - Celery beat (scheduler)"
	@echo "  make frontend   - Vite dev server on :5173"
	@echo "  make eval       - run the agent golden-query harness"
	@echo "  make health     - check which services are up"
	@echo "  Note: Qdrant is Docker-based; start it separately if you need"
	@echo "        Discovery/thematic search (insights work without it)."

infra:
	brew services start redis
	brew services start ollama
	@echo "Starting Docker (colima) + Qdrant..."
	colima status >/dev/null 2>&1 || colima start
	docker-compose up -d qdrant
	@echo "Redis + Ollama + Qdrant started. (Ensure 'ollama pull nomic-embed-text' has been run once.)"

infra-stop:
	brew services stop redis || true
	brew services stop ollama || true
	docker-compose stop qdrant || true

backend:
	cd $(BACKEND) && .venv/bin/python -m uvicorn src.main:app --host 0.0.0.0 --port 8001 --reload

worker:
	cd $(BACKEND) && .venv/bin/celery -A src.celery_app worker --loglevel=info --concurrency=2

beat:
	cd $(BACKEND) && .venv/bin/celery -A src.celery_app beat --loglevel=info

frontend:
	cd frontend && npx vite --port 5173

eval:
	cd $(BACKEND) && .venv/bin/python scripts/eval_agent.py

seed:
	cd $(BACKEND) && .venv/bin/python -c "from src.etl.bootstrap_task import bootstrap; print(bootstrap.run())"

health:
	@printf "API :8001        " && (curl -s -o /dev/null -w "%{http_code}\n" -m 3 http://localhost:8001/health || echo DOWN)
	@printf "Frontend :5173   " && (curl -s -o /dev/null -w "%{http_code}\n" -m 3 http://localhost:5173 || echo DOWN)
	@printf "Redis :6379      " && (nc -z -G2 localhost 6379 && echo OPEN || echo DOWN)
	@printf "Ollama :11434    " && (curl -s -o /dev/null -w "%{http_code}\n" -m 3 http://localhost:11434/api/tags || echo DOWN)
	@printf "Qdrant :6333     " && (nc -z -G2 localhost 6333 && echo OPEN || echo "DOWN (run: docker-compose up -d qdrant)")
	@printf "Celery worker    " && (pgrep -f "celery.*worker" >/dev/null && echo UP || echo DOWN)
	@printf "Celery beat      " && (pgrep -f "celery.*beat" >/dev/null && echo UP || echo DOWN)
