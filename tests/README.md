# Tests

## Quick Start

```bash
# Unit tests (no infrastructure needed)
uv run pytest -m unit

# Integration tests (requires Redis + RabbitMQ)
uv run pytest -m integration

# Run all tests
uv run pytest
```

## Test Categories

**Unit Tests** (`-m unit`)
- Fast, no external dependencies
- Mock all external connections

**Integration Tests** (`-m integration`)
- Requires Redis/RabbitMQ running
- Tests complete event flow through real systems

## Infrastructure Setup

```bash
# Start test infrastructure
docker-compose -f tests/docker-compose.yml up -d

# Stop infrastructure
docker-compose -f tests/docker-compose.yml down
```

## Running Specific Tests

```bash
# Redis tests only
uv run pytest -m redis

# RabbitMQ tests only  
uv run pytest -m rabbitmq

# Single test file
uv run pytest tests/unit/test_models.py

# With verbose output
uv run pytest -v

# Debug with pdb
uv run pytest --pdb
```

## Environment Variables

```bash
# Optional: Override default URLs
export REDIS_URL="redis://localhost:6379"
export RABBITMQ_URL="amqp://guest:guest@localhost:5672/"
```
