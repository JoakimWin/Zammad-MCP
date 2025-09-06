# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common Development Commands

```bash
# Setup development environment
./scripts/setup.sh  # macOS/Linux
.\scripts\setup.ps1  # Windows

# Run the MCP server

python -m mcp_zammad --mode http --host localhost --port 8443 --ssl --ssl-generate

python -m mcp_zammad  # stdio mode (default)
python -m mcp_zammad --mode http  # HTTP mode
python -m mcp_zammad --mode http --host 0.0.0.0 --port 8080  # custom host/port
python -m mcp_zammad --mode http --port 8443 --ssl --ssl-generate  # HTTPS with self-signed cert
python -m mcp_zammad --mode http --port 8443 --ssl --ssl-cert cert.pem --ssl-key key.pem  # HTTPS with custom cert
uv run python -m mcp_zammad --mode http --ssl --ssl-generate
uvx --from git+https://github.com/basher83/zammad-mcp.git mcp-zammad

# Run tests
uv run pytest
uv run pytest --cov=mcp_zammad --cov-fail-under=90  # with 90% coverage requirement
uv run pytest tests/test_server.py::test_search_tickets  # run specific test

# Code quality checks (use ./scripts/quality-check.sh for all)
uv run ruff format mcp_zammad tests  # format code
uv run ruff check mcp_zammad tests --fix  # lint with auto-fix
uv run mypy mcp_zammad  # type check

# Security checks
uv run pip-audit  # check for vulnerabilities
uv run bandit -r mcp_zammad --severity-level high  # security analysis
uv run semgrep --config=auto mcp_zammad  # static analysis
uv run safety scan --output json  # dependency security scan

# Build and publish
uv build
docker build -t ghcr.io/basher83/zammad-mcp:latest .

# Development workflow
./scripts/quality-check.sh  # run all checks before commit
```

## High-Level Architecture

This MCP server provides Zammad ticket system integration following a clean three-layer architecture:

```
MCP Protocol Layer (server.py)
    ↓
API Client Layer (client.py)  
    ↓
Data Model Layer (models.py)
```

**HTTP/HTTPS/SSE Support** (NEW):
- `http_server.py`: FastAPI wrapper providing HTTP/HTTPS/SSE access to MCP functionality
- `cli.py`: Unified CLI supporting both stdio and HTTP/HTTPS modes
- `ssl_utils.py`: SSL certificate generation and management
- Endpoints: `/health`, `/mcp/call`, `/mcp/stream` (SSE)
- HTTPS support with self-signed or custom certificates for Claude Desktop HTTP connector

### Core Components

**`server.py`** - MCP Server Implementation (FastMCP)
- **Tools**: 18 operations (tickets, users, organizations, attachments)
- **Resources**: 4 URI-based endpoints (`zammad://ticket/{id}`, `zammad://user/{id}`, etc.)
- **Prompts**: 3 pre-configured analysis templates
- **Lifecycle**: Manages global Zammad client with proper initialization/cleanup
- **Pattern**: Sentinel object (`_UNINITIALIZED`) for type-safe client state

**`client.py`** - Zammad API Client Wrapper
- Wraps `zammad_py` library with enhanced functionality
- Handles authentication (API token, OAuth2, username/password)
- Docker secrets support via `*_FILE` environment variables
- Security: URL validation (SSRF protection), input sanitization
- Caching: Groups, states, priorities cached for performance

**`models.py`** - Pydantic Data Models
- Type-safe models for all Zammad entities
- Handles Zammad API quirks (expand parameter returns strings not objects)
- Union types: `group: GroupBrief | str | None` for flexibility
- HTML sanitization built into validators

### Critical Implementation Details

**Global Client Management**
```python
# DO NOT create new ZammadClient instances in tools
# Always use the shared global client:
client = get_zammad_client()  # Type-safe accessor
```

**Zammad API Expand Behavior**
When using `expand=True`, Zammad returns string representations instead of objects:
- Returns: `"group": "Users"` (string)
- Not: `"group": {"id": 1, "name": "Users"}` (object)
- All models handle both formats via union types

**Async Context**
FastMCP handles its own event loop - never wrap `mcp.run()` in `asyncio.run()`

## Environment Configuration

The server requires Zammad API credentials via environment variables:

```bash
# Required: Zammad instance URL (must include /api/v1)
ZAMMAD_URL=https://your-instance.zammad.com/api/v1

# Authentication (choose one):
ZAMMAD_HTTP_TOKEN=your-api-token  # Recommended
# or
ZAMMAD_OAUTH2_TOKEN=your-oauth2-token
# or
ZAMMAD_USERNAME=your-username
ZAMMAD_PASSWORD=your-password
```

## Testing Strategy

**Coverage**: 90.08% (target: 90% ✓)

### Test Structure
```python
# tests/test_server.py - Main test suite
# Key fixtures:
@pytest.fixture
def mock_client() -> MagicMock  # Mocked ZammadClient
def ticket_factory() -> Callable  # Generate test tickets
def user_factory() -> Callable  # Generate test users

# Test patterns:
- Mock ZammadClient for all tests (no real API calls)
- Parametrize for multiple scenarios
- Test both success and error paths
- Factory fixtures for flexible test data
```

### Running Tests
```bash
uv run pytest tests/test_server.py -v  # verbose output
uv run pytest -k "test_search"  # run tests matching pattern
uv run pytest --cov=mcp_zammad --cov-report=html  # HTML coverage report
```

## Code Quality Standards

**Python**: 3.10+ required (use modern type hints)
**Line Length**: 120 characters
**Formatting**: Ruff (automatic fixes with --fix)
**Type Checking**: MyPy with strict mode

### Key Patterns
```python
# Modern type hints (3.10+)
list[str] not List[str]
str | None not Optional[str]

# Avoid parameter shadowing
article_type not type  # 'type' is a builtin

# Type narrowing for safety
client = get_zammad_client()  # Returns ZammadClient, not object
```

## Adding New Features

### New Tool Example
```python
# In server.py
@mcp.tool()
async def my_new_tool(param: str) -> dict:
    """Tool description for MCP."""
    client = get_zammad_client()  # Always use global client
    result = client.some_api_call(param)
    return MyModel(**result).model_dump()  # Return Pydantic model
```

### New Resource Example  
```python
# In server.py resource handler
if uri.startswith("zammad://myentity/"):
    entity_id = uri.split("/")[-1]
    client = get_zammad_client()
    data = client.get_myentity(entity_id)
    return json.dumps(MyEntityModel(**data).model_dump())
```

## Claude Desktop Configuration

Add to your Claude Desktop config:

```json
{
  "mcpServers": {
    "zammad": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/basher83/zammad-mcp.git", "mcp-zammad"],
      "env": {
        "ZAMMAD_URL": "https://your-instance.zammad.com/api/v1",
        "ZAMMAD_HTTP_TOKEN": "your-api-token"
      }
    }
  }
}
```

Or with Docker:
```json
{
  "mcpServers": {
    "zammad": {
      "command": "docker",
      "args": ["run", "--rm", "-i", 
               "-e", "ZAMMAD_URL=https://your-instance.zammad.com/api/v1",
               "-e", "ZAMMAD_HTTP_TOKEN=your-api-token",
               "ghcr.io/basher83/zammad-mcp:latest"]
    }
  }
}
```

**Note**: MCP uses stdio (stdin/stdout), not HTTP. The `-i` flag is required.

## Current Limitations

### Performance
- Synchronous client initialization blocks server startup
- No connection pooling for API requests

### Missing Features  
- No custom field handling
- No bulk operations (update multiple tickets)
- No webhook/real-time update support
- No time tracking functionality
- No rate limiting implementation
- No audit logging

### Recent Fixes (v0.1.3)
✅ Test coverage increased to 90.08%
✅ Attachment support added (list and download)
✅ Caching for groups, states, priorities
✅ Pagination for ticket stats (memory optimization)
✅ URL validation with SSRF protection
✅ HTML sanitization in models
✅ Docker secrets support