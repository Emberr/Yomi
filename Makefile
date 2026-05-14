.PHONY: dev test lint typecheck bootstrap backup

dev:
	docker compose up -d

test:
	@if command -v uv >/dev/null 2>&1; then \
		cd backend && uv run pytest; \
	else \
		cd backend && python3 -m pytest; \
	fi
	@if command -v uv >/dev/null 2>&1; then \
		cd ingestion && uv run pytest; \
	else \
		cd ingestion && python3 -m pytest; \
	fi

lint:
	@printf '%s\n' 'Checking for unresolved merge conflict markers...'
	@if rg -n '^(<<<<<<<|=======|>>>>>>>)' . --glob '!frontend/package-lock.json'; then \
		printf '%s\n' 'Unresolved merge conflict marker found.'; \
		exit 1; \
	fi
	@if command -v uv >/dev/null 2>&1; then \
		cd backend && uv run python -m compileall yomi tests; \
	else \
		cd backend && python3 -m compileall yomi tests; \
	fi
	@if command -v uv >/dev/null 2>&1; then \
		cd ingestion && uv run python -m compileall ingest.py tests; \
	else \
		cd ingestion && python3 -m compileall ingest.py tests; \
	fi
	cd frontend && npm ci && npm run lint

typecheck:
	@if command -v uv >/dev/null 2>&1; then \
		cd backend && uv run python -m compileall yomi tests; \
	else \
		cd backend && python3 -m compileall yomi tests; \
	fi
	@if command -v uv >/dev/null 2>&1; then \
		cd ingestion && uv run python -m compileall ingest.py tests; \
	else \
		cd ingestion && python3 -m compileall ingest.py tests; \
	fi
	cd frontend && npm ci && npm run typecheck

bootstrap:
	@printf '%s\n' 'Phase 1 stub: bootstrap is out of scope until admin/auth setup exists.'
	@exit 1

backup:
	@printf '%s\n' 'Phase 1 stub: backup is out of scope until runtime data and checkpoint flow are defined.'
	@exit 1
