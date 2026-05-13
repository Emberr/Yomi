.PHONY: dev test lint typecheck bootstrap backup

REQUIRED_FILES := AGENTS.md README.md LICENSE LICENSES.md SECURITY.md CONTRIBUTING.md .env.example .gitignore Makefile docker-compose.yml
REQUIRED_DIRS := frontend backend ingestion nginx deploy docs/agent docs/architecture
CHECK_FILES := README.md LICENSE LICENSES.md SECURITY.md CONTRIBUTING.md .env.example .gitignore Makefile docker-compose.yml

dev:
	@printf '%s\n' 'M0.2 placeholder: dev server is not available until app scaffolds and Compose services are added.'
	@exit 1

test:
	@printf '%s\n' 'Checking Phase 0 repository scaffold...'
	@for path in $(REQUIRED_FILES); do \
		if [ ! -f "$$path" ]; then \
			printf 'Missing required file: %s\n' "$$path"; \
			exit 1; \
		fi; \
	done
	@for path in $(REQUIRED_DIRS); do \
		if [ ! -d "$$path" ]; then \
			printf 'Missing required directory: %s\n' "$$path"; \
			exit 1; \
		fi; \
	done
	@printf '%s\n' 'Phase 0 repository scaffold files and directories are present.'

lint:
	@printf '%s\n' 'Checking Phase 0 scaffold files for unresolved merge conflict markers...'
	@if grep -n -E '^(<<<<<<<|=======|>>>>>>>)' $(CHECK_FILES); then \
		printf '%s\n' 'Unresolved merge conflict marker found.'; \
		exit 1; \
	fi
	@printf '%s\n' 'No unresolved merge conflict markers found in scaffold files.'

typecheck:
	@printf '%s\n' 'M0.2 placeholder: typecheck is not available until backend/frontend projects are scaffolded.'
	@exit 1

bootstrap:
	@printf '%s\n' 'M0.2 placeholder: bootstrap is not available until project dependencies and setup flow are defined.'
	@exit 1

backup:
	@printf '%s\n' 'M0.2 placeholder: backup is not available until runtime data directories and database layout exist.'
	@exit 1
