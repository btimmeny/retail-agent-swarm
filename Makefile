# Makefile for retail-agent-swarm

.PHONY: help install dev test lint format typecheck clean docker-up docker-down

.DEFAULT_GOAL := help

help:
	@echo "Usage: make <target>"
	@echo ""
	@echo "Targets:"
	@echo "  help        Show this help message"
	@echo "  install     Install Python dependencies"
	@echo "  dev         Start development server (uvicorn app:app --reload)"
	@echo "  test        Run tests with pytest"
	@echo "  lint        Run linter (ruff)"
	@echo "  format      Run code formatter (ruff format + black)"
	@echo "  typecheck   Run type checker (mypy)"
	@echo "  clean       Remove Python build/test artifacts"
	@echo "  docker-up   Start services using docker-compose"
	@echo "  docker-down Stop services using docker-compose"

install:
	pip install --upgrade pip
	pip install -r requirements-dev.txt

dev:
	uvicorn app:app --reload

test:
	pytest

lint:
	ruff . 

format:
	ruff format .
	black .

typecheck:
	mypy .

clean:
	find . -type d -name '__pycache__' -exec rm -rf {} +
	find . -type d -name '.mypy_cache' -exec rm -rf {} +
	find . -type d -name '.pytest_cache' -exec rm -rf {} +
	find . -type d -name '.ruff_cache' -exec rm -rf {} +
	rm -rf .mypy_cache .pytest_cache .ruff_cache
	rm -rf dist build *.egg-info

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down
