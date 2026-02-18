.PHONY: help install test lint format clean docker-up docker-down migrate

help:
	@echo "Available commands:"
	@echo "  make install      - Install dependencies with Poetry"
	@echo "  make test         - Run tests with pytest"
	@echo "  make lint         - Run linting with ruff"
	@echo "  make format       - Format code with black and ruff"
	@echo "  make clean        - Clean up generated files"
	@echo "  make docker-up    - Start Docker services"
	@echo "  make docker-down  - Stop Docker services"
	@echo "  make migrate      - Run database migrations"

install:
	poetry install

test:
	poetry run pytest

test-cov:
	poetry run pytest --cov=src/doc_healing --cov-report=html

lint:
	poetry run ruff check src tests
	poetry run mypy src

format:
	poetry run black src tests
	poetry run ruff check --fix src tests

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
	find . -type d -name "htmlcov" -exec rm -rf {} +
	find . -type f -name ".coverage" -delete

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f

migrate:
	poetry run alembic upgrade head

migrate-create:
	poetry run alembic revision --autogenerate -m "$(message)"

dev:
	poetry run uvicorn doc_healing.api.main:app --reload --host 0.0.0.0 --port 8000
