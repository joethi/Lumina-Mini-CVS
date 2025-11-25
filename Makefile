# Makefile for mini-lumina

.PHONY: help install test run-backend run-frontend docker-build docker-up docker-down clean lint format

help:
	@echo "Available commands:"
	@echo "  make install        - Install dependencies"
	@echo "  make test          - Run tests with coverage"
	@echo "  make run-backend   - Run FastAPI backend"
	@echo "  make run-frontend  - Run Streamlit frontend"
	@echo "  make docker-build  - Build Docker images"
	@echo "  make docker-up     - Start services with docker-compose"
	@echo "  make docker-down   - Stop services"
	@echo "  make clean         - Clean cache and build files"
	@echo "  make lint          - Run linting"
	@echo "  make format        - Format code"

install:
	pip install -r requirements.txt

test:
	pytest app/tests/ -v --cov=app --cov-report=term-missing --cov-report=html

test-unit:
	pytest app/tests/ -v -m "not integration"

test-integration:
	pytest app/tests/ -v -m integration

run-backend:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

run-frontend:
	streamlit run streamlit_app/app.py

docker-build:
	docker-compose build

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .pytest_cache .coverage htmlcov/ dist/ build/

lint:
	@echo "Running linting..."
	@pip list | grep -q flake8 || pip install flake8
	flake8 app/ --max-line-length=100 --ignore=E501,W503

format:
	@echo "Formatting code..."
	@pip list | grep -q black || pip install black
	black app/ streamlit_app/ --line-length=100

ingest:
	@echo "Usage: make ingest FILE=path/to/file"
	python -m app.ingestion $(FILE)

eval:
	python -m app.eval --dataset eval_dataset.csv --output eval_report.json
