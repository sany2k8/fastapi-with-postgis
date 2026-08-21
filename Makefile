.PHONY: help install seed dev-api dev-ui lint typecheck test check migrate ingest-roads manage

help:
	@echo "Places Finder — a PostGIS learning app"
	@echo ""
	@echo "  make install    Install backend (uv) and frontend (npm) deps"
	@echo "  make migrate    Apply Alembic migrations"
	@echo "  make seed       Seed the database with sample data"
	@echo "  make ingest-roads  Fetch OSM road graphs (Bangladesh routing)"
	@echo "  make manage        Data CLI: add places/neighbourhoods/city roads (pass ARGS=...)"
	@echo "  make dev-api    Run the FastAPI backend  (:8850)"
	@echo "  make dev-ui     Run the Vite frontend     (:5199)"
	@echo "  make lint       Ruff format + check"
	@echo "  make typecheck  mypy (backend) + tsc (frontend)"
	@echo "  make test       pytest"
	@echo "  make check      lint + typecheck + test (the gate)"

install:
	cd backend && uv venv && uv pip install -e ".[dev]"
	cd frontend && npm install

migrate:
	cd backend && uv run alembic upgrade head

seed:
	cd backend && uv run python -m scripts.seed

ingest-roads:
	cd backend && uv run python -m scripts.ingest_roads

# Data management CLI. Examples:
#   make manage ARGS="stats"
#   make manage ARGS='add-place "Blue Bottle" cafe --at 37.776,-122.423'
#   make manage ARGS='add-city-roads sylhet --bbox 91.855,24.885,91.895,24.915'
manage:
	cd backend && uv run python -m scripts.manage $(ARGS)

dev-api:
	cd backend && uv run uvicorn app.main:app --reload --port 8850

dev-ui:
	cd frontend && npm run dev

lint:
	cd backend && uv run ruff format . && uv run ruff check .

typecheck:
	cd backend && uv run mypy app
	cd frontend && npx tsc --noEmit

test:
	cd backend && uv run pytest -q

check: lint typecheck test
