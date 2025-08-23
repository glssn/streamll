#!/bin/bash
# scripts/test-env.sh
set -e

echo "🏗️  Setting up test infrastructure..."

# Start services
docker-compose -f docker-compose.test.yml up -d

# Wait for health checks
echo "⏳ Waiting for services to be healthy..."
timeout 60s bash -c 'until docker-compose -f docker-compose.test.yml ps | grep -E "(redis-test.*healthy|rabbitmq-test.*healthy)" | wc -l | grep -q "2"; do sleep 2; done'

echo "✅ Test infrastructure ready"

# Set environment variables for tests
export REDIS_URL="redis://localhost:6379"
export RABBITMQ_URL="amqp://streamll:streamll_test@localhost:5672/"

echo "🧪 Running integration tests..."
REDIS_URL="$REDIS_URL" RABBITMQ_URL="$RABBITMQ_URL" uv run pytest tests/integration/ -v

echo "🧹 Cleaning up..."
docker-compose -f docker-compose.test.yml down -v