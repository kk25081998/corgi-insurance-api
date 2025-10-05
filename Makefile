.PHONY: dev seed test build up down clean

# Development commands
dev:
	uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

seed:
	python3 app/data/generate_policies.py

test:
	pytest -q

# Docker commands
build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

# Combined commands
dev-setup: build up seed
	@echo "Development environment ready!"
	@echo "Run 'make dev' to start the API server"

# Cleanup
clean:
	docker compose down -v
	rm -rf data/*.db data/*.csv
	@echo "Cleaned up database and generated files"
