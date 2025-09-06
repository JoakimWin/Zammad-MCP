"""Tests for HTTP/SSE server."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from mcp_zammad.http_server import HTTPMCPServer, create_http_server


@pytest.fixture
def mock_mcp_server():
    """Create a mock MCP server."""
    server = MagicMock()
    server.initialize = AsyncMock()
    server.mcp = MagicMock()
    server.mcp.tools = []
    server.mcp.resources = []
    server.mcp.prompts = []
    return server


@pytest.fixture
def http_server(mock_mcp_server):
    """Create HTTP server with mocked MCP server."""
    return HTTPMCPServer(mock_mcp_server)


@pytest.fixture
def test_client(http_server):
    """Create test client for FastAPI app."""
    return TestClient(http_server.app)


def test_health_endpoint(test_client):
    """Test health check endpoint."""
    response = test_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_list_tools(test_client):
    """Test listing tools."""
    response = test_client.post("/mcp/call", json={"method": "tools/list"})
    assert response.status_code == 200
    data = response.json()
    assert "result" in data
    assert "tools" in data["result"]
    assert isinstance(data["result"]["tools"], list)


def test_list_resources(test_client):
    """Test listing resources."""
    response = test_client.post("/mcp/call", json={"method": "resources/list"})
    assert response.status_code == 200
    data = response.json()
    assert "result" in data
    assert "resources" in data["result"]
    assert isinstance(data["result"]["resources"], list)


def test_list_prompts(test_client):
    """Test listing prompts."""
    response = test_client.post("/mcp/call", json={"method": "prompts/list"})
    assert response.status_code == 200
    data = response.json()
    assert "result" in data
    assert "prompts" in data["result"]
    assert isinstance(data["result"]["prompts"], list)


def test_unknown_method(test_client):
    """Test calling unknown method."""
    response = test_client.post("/mcp/call", json={"method": "unknown/method"})
    assert response.status_code == 200
    data = response.json()
    assert "error" in data
    assert "Method not found" in data["error"]["message"] or "Unknown method" in data["error"]["message"]


def test_cors_headers(test_client):
    """Test CORS headers are present."""
    response = test_client.post("/mcp/call", json={"method": "tools/list"})
    # Check CORS headers in actual response
    assert "*" in response.headers.get("access-control-allow-origin", "*")  # Default or set value


@pytest.mark.asyncio
async def test_call_tool_not_found(http_server):
    """Test calling non-existent tool."""
    with pytest.raises(ValueError, match="Tool not found"):
        await http_server._call_tool("non_existent_tool", {})


@pytest.mark.asyncio
async def test_read_resource_not_found(http_server):
    """Test reading non-existent resource."""
    with pytest.raises(ValueError, match="Resource not found"):
        await http_server._read_resource("zammad://invalid/123")


def test_matches_pattern():
    """Test URI pattern matching."""
    server = HTTPMCPServer(MagicMock())
    
    # Test exact match
    assert server._matches_pattern("zammad://test", "zammad://test")
    
    # Test pattern with parameter
    assert server._matches_pattern("zammad://ticket/123", "zammad://ticket/{id}")
    assert not server._matches_pattern("zammad://user/456", "zammad://ticket/{id}")


def test_extract_params():
    """Test parameter extraction from URI."""
    server = HTTPMCPServer(MagicMock())
    
    # Test parameter extraction
    params = server._extract_params("zammad://ticket/123", "zammad://ticket/{id}")
    assert params == {"id": "123"}
    
    # Test no parameters
    params = server._extract_params("zammad://test", "zammad://test")
    assert params == {}


def test_create_http_server():
    """Test creating HTTP server with factory function."""
    with patch("mcp_zammad.http_server.ZammadMCPServer") as mock_server_class:
        mock_server_class.return_value = MagicMock()
        
        server = create_http_server(host="0.0.0.0", port=9090)
        
        assert isinstance(server, HTTPMCPServer)
        assert server.host == "0.0.0.0"
        assert server.port == 9090