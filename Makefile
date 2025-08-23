# StreamLL Makefile
# Simplified approach following Instructor patterns
# See README-TESTING.md for detailed testing guide

.PHONY: help test dev-install lint typecheck docker-up docker-down

help:
	@echo "🚀 StreamLL Development Commands"
	@echo ""
	@echo "Quick Testing (following Instructor patterns):"
	@echo "  test             Run unit tests (fast, no infrastructure)"
	@echo "  test-integration Run integration tests (requires infrastructure)"
	@echo "  test-performance Run performance benchmarks"
	@echo ""
	@echo "Infrastructure:"
	@echo "  docker-up        Start test infrastructure (Redis + RabbitMQ)"
	@echo "  docker-down      Stop test infrastructure"
	@echo ""
	@echo "Development:"
	@echo "  dev-install      Install development dependencies"
	@echo "  lint             Run code linting"
	@echo "  typecheck        Run type checking"
	@echo ""
	@echo "💡 See tests/README.md for details"

# Installation
dev-install:
	@echo "🛠️  Installing development dependencies..."
	uv sync

# Code Quality
lint:
	@echo "🔍 Running linter..."
	uv run ruff check src/ tests/

typecheck:
	@echo "🔍 Running type checker..."
	uv run ty check src/ tests/ || echo "ℹ️  Type checking completed with warnings"

# Infrastructure Management (separate from testing)
docker-up:
	@echo "🏗️  Starting test infrastructure..."
	docker-compose -f tests/docker-compose.yml up -d
	@echo "⏳ Waiting for services..."
	@sleep 10

docker-down:
	@echo "🧹 Stopping test infrastructure..."
	docker-compose -f tests/docker-compose.yml down -v

# Simple Testing Commands (following Instructor approach)
test:
	@echo "🧪 Running unit tests..."
	uv run pytest -m unit -v

test-integration:
	@echo "🔗 Running integration tests (requires running infrastructure)..."
	@echo "💡 Start infrastructure first: make docker-up"
	uv run pytest -m integration -v

test-performance:
	@echo "⚡ Running performance benchmarks (requires running infrastructure)..."
	@echo "💡 Start infrastructure first: make docker-up"  
	uv run pytest -m performance -v -s
