.PHONY: help install test run run-http run-debug clean

help:
	@echo "Available commands:"
	@echo "  make install    - Install dependencies"
	@echo "  make test       - Run tests"
	@echo "  make run        - Run server in stdio mode"
	@echo "  make run-http   - Run server in HTTP mode"
	@echo "  make run-debug  - Run HTTP server with debug logging"
	@echo "  make clean      - Clean generated files"

install:
	uv pip install -e .

test:
	uv run pytest --cov=mcp_zammad

run:
	python -m mcp_zammad

run-http:
	python -m mcp_zammad --mode http --host 127.0.0.1 --port 8080

run-debug:
	python -m mcp_zammad --mode http --host 127.0.0.1 --port 8080 --log-level DEBUG

clean:
	rm -rf __pycache__ .pytest_cache .coverage htmlcov
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete