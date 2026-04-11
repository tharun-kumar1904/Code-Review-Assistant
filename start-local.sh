#!/bin/bash

echo "=============================================================="
echo "  AI Code Review Assistant - Local Development Startup"
echo "=============================================================="
echo ""
echo "Bringing up the complete infrastructure using Docker Compose..."
echo "This will start PostgreSQL, Redis, FastAPI backend, React frontend,"
echo "Celery workers, and monitoring tools (Prometheus + Grafana)."
echo ""

cd infrastructure
docker-compose up -d --build

echo ""
echo "=============================================================="
echo "  System is starting! Allow local containers to boot up."
echo ""
echo "  Local Dashboard:   http://localhost:3000"
echo "  API Documentation: http://localhost:8000/docs"
echo "  Grafana Metrics:   http://localhost:3001"
echo ""
echo "  To stop the system later, run:"
echo "    cd infrastructure && docker-compose down"
echo "=============================================================="
