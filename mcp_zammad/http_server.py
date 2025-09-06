"""HTTP/SSE server wrapper for Zammad MCP server."""

import asyncio
import json
import logging
import uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .server import ZammadMCPServer

logger = logging.getLogger(__name__)


class MCPRequest(BaseModel):
    """MCP request model for HTTP endpoint."""

    method: str
    params: dict[str, Any] | None = None


class MCPResponse(BaseModel):
    """MCP response model for HTTP endpoint."""

    result: Any | None = None
    error: dict[str, Any] | None = None


class HTTPMCPServer:
    """HTTP/HTTPS/SSE wrapper for MCP server."""

    def __init__(self, mcp_server: ZammadMCPServer, host: str = "127.0.0.1", port: int = 8080, ssl_config: dict[str, Any] | None = None):
        """Initialize HTTP/HTTPS MCP server.

        Args:
            mcp_server: The Zammad MCP server instance
            host: Host to bind to
            port: Port to bind to
            ssl_config: Optional SSL configuration with 'cert' and 'key' paths
        """
        self.mcp_server = mcp_server
        self.host = host
        self.port = port
        self.ssl_config = ssl_config
        
        # Create lifespan context manager
        @asynccontextmanager
        async def lifespan(app: FastAPI) -> AsyncIterator[None]:
            """Lifespan context manager for FastAPI."""
            # Startup
            await self.mcp_server.initialize()
            protocol = "https" if self.ssl_config else "http"
            logger.info(f"MCP server started on {protocol}://{self.host}:{self.port}")
            yield
            # Shutdown
            logger.info("MCP server shutting down")
        
        self.app = FastAPI(
            title="Zammad MCP HTTP Server", 
            version="0.1.0",
            lifespan=lifespan
        )
        self._setup_middleware()
        self._setup_routes()

    def _setup_middleware(self) -> None:
        """Setup FastAPI middleware."""
        # Configure CORS
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # Configure appropriately for production
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def _setup_routes(self) -> None:
        """Setup HTTP routes."""

        @self.app.get("/health")
        async def health() -> dict[str, str]:
            """Health check endpoint."""
            return {"status": "healthy"}

        @self.app.post("/mcp/call")
        async def mcp_call(request: MCPRequest) -> MCPResponse:
            """Execute MCP method call.

            This endpoint handles synchronous MCP calls.
            """
            try:
                # Get the appropriate handler based on method
                if request.method == "tools/list":
                    result = await self._list_tools()
                elif request.method == "resources/list":
                    result = await self._list_resources()
                elif request.method == "prompts/list":
                    result = await self._list_prompts()
                elif request.method == "tools/call":
                    # MCP standard: tools/call with name and arguments in params
                    params = request.params or {}
                    tool_name = params.get("name")
                    if not tool_name:
                        raise HTTPException(status_code=400, detail="Missing 'name' parameter in tools/call")
                    tool_arguments = params.get("arguments", {})
                    result = await self._call_tool(tool_name, tool_arguments)
                elif request.method.startswith("resources/read/"):
                    resource_uri = request.method.replace("resources/read/", "")
                    result = await self._read_resource(resource_uri)
                elif request.method.startswith("prompts/get/"):
                    prompt_name = request.method.replace("prompts/get/", "")
                    result = await self._get_prompt(prompt_name, request.params or {})
                else:
                    raise HTTPException(status_code=404, detail=f"Method not found: {request.method}")

                return MCPResponse(result=result)

            except Exception as e:
                logger.error(f"Error handling MCP call: {e}")
                return MCPResponse(error={"code": -32603, "message": str(e)})

        @self.app.post("/mcp/stream")
        async def mcp_stream(request: MCPRequest) -> StreamingResponse:
            """Execute MCP method call with SSE streaming.

            This endpoint handles streaming MCP calls using Server-Sent Events.
            """

            async def generate() -> AsyncIterator[str]:
                """Generate SSE stream."""
                try:
                    # Send initial connection event
                    yield f"event: connected\ndata: {json.dumps({'session_id': str(uuid.uuid4())})}\n\n"

                    # Process the request
                    if request.method == "tools/call":
                        # MCP standard: tools/call with name and arguments in params
                        params = request.params or {}
                        tool_name = params.get("name")
                        if not tool_name:
                            yield f"event: error\ndata: {json.dumps({'error': 'Missing name parameter in tools/call'})}\n\n"
                            return
                        tool_arguments = params.get("arguments", {})
                        # For streaming tools, we might need to handle them differently
                        result = await self._call_tool(tool_name, tool_arguments)
                        # Convert to JSON-serializable format
                        if hasattr(result, '__dict__'):
                            result = result.__dict__
                        elif isinstance(result, list) and len(result) > 0:
                            # Handle list of results (like from Claude tools)
                            serializable_result = []
                            for item in result:
                                if hasattr(item, '__dict__'):
                                    serializable_result.append(item.__dict__)
                                elif hasattr(item, 'model_dump'):
                                    serializable_result.append(item.model_dump())
                                else:
                                    serializable_result.append(item)
                            result = serializable_result
                        yield f"event: result\ndata: {json.dumps(result, default=str)}\n\n"
                    else:
                        # For non-streaming methods, just return the result
                        result = await self._handle_method(request.method, request.params)
                        yield f"event: result\ndata: {json.dumps(result)}\n\n"

                    # Send completion event
                    yield f"event: done\ndata: {json.dumps({'status': 'completed'})}\n\n"

                except Exception as e:
                    logger.error(f"Error in SSE stream: {e}")
                    error_data = {"error": {"code": -32603, "message": str(e)}}
                    yield f"event: error\ndata: {json.dumps(error_data)}\n\n"

            return StreamingResponse(
                generate(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",  # Disable proxy buffering
                },
            )

    async def _handle_method(self, method: str, params: dict[str, Any] | None) -> Any:
        """Handle MCP method call."""
        if method == "tools/list":
            return await self._list_tools()
        elif method == "resources/list":
            return await self._list_resources()
        elif method == "prompts/list":
            return await self._list_prompts()
        elif method.startswith("tools/call/"):
            tool_name = method.replace("tools/call/", "")
            return await self._call_tool(tool_name, params or {})
        elif method.startswith("resources/read/"):
            resource_uri = method.replace("resources/read/", "")
            return await self._read_resource(resource_uri)
        elif method.startswith("prompts/get/"):
            prompt_name = method.replace("prompts/get/", "")
            return await self._get_prompt(prompt_name, params or {})
        else:
            raise ValueError(f"Unknown method: {method}")

    async def _list_tools(self) -> dict[str, Any]:
        """List available tools."""
        # Use the list_tools method from FastMCP
        tools_list = await self.mcp_server.mcp.list_tools()
        tools = []
        for tool in tools_list:
            tools.append(
                {
                    "name": tool.name,
                    "description": tool.description or "",
                    "inputSchema": tool.inputSchema or {},
                }
            )
        return {"tools": tools}

    async def _list_resources(self) -> dict[str, Any]:
        """List available resources."""
        # Use the list_resources method from FastMCP
        resources_list = await self.mcp_server.mcp.list_resources()
        resources = []
        for resource in resources_list:
            resources.append(
                {
                    "uri": resource.uri,
                    "name": resource.name or "",
                    "description": resource.description or "",
                    "mimeType": resource.mimeType or "text/plain",
                }
            )
        return {"resources": resources}

    async def _list_prompts(self) -> dict[str, Any]:
        """List available prompts."""
        # Use the list_prompts method from FastMCP
        prompts_list = await self.mcp_server.mcp.list_prompts()
        prompts = []
        for prompt in prompts_list:
            prompts.append(
                {
                    "name": prompt.name,
                    "description": prompt.description or "",
                    "arguments": getattr(prompt, 'arguments', []) or [],
                }
            )
        return {"prompts": prompts}

    async def _call_tool(self, tool_name: str, params: dict[str, Any]) -> Any:
        """Call a tool."""
        # Use the call_tool method from FastMCP
        try:
            result = await self.mcp_server.mcp.call_tool(tool_name, params)
            # Convert result to dict if it's a model
            if hasattr(result, 'model_dump'):
                return result.model_dump()
            elif hasattr(result, 'dict'):
                return result.dict()
            return result
        except Exception as e:
            raise ValueError(f"Error calling tool {tool_name}: {str(e)}")

    async def _read_resource(self, resource_uri: str) -> Any:
        """Read a resource."""
        # Use the read_resource method from FastMCP
        try:
            result = await self.mcp_server.mcp.read_resource(resource_uri)
            return {
                "contents": [
                    {
                        "uri": resource_uri,
                        "mimeType": result.mimeType or "text/plain",
                        "text": result.text or ""
                    }
                ]
            }
        except Exception as e:
            raise ValueError(f"Error reading resource {resource_uri}: {str(e)}")

    async def _get_prompt(self, prompt_name: str, params: dict[str, Any]) -> Any:
        """Get a prompt."""
        # Use the get_prompt method from FastMCP
        try:
            result = await self.mcp_server.mcp.get_prompt(prompt_name, params)
            # Convert result to dict if it's a model
            if hasattr(result, 'model_dump'):
                return result.model_dump()
            elif hasattr(result, 'dict'):
                return result.dict()
            return result
        except Exception as e:
            raise ValueError(f"Error getting prompt {prompt_name}: {str(e)}")

    def _matches_pattern(self, uri: str, pattern: str) -> bool:
        """Check if URI matches resource pattern."""
        # Simple pattern matching for now
        if "{" in pattern:
            base_pattern = pattern.split("{")[0]
            return uri.startswith(base_pattern)
        return uri == pattern

    def _extract_params(self, uri: str, pattern: str) -> dict[str, Any]:
        """Extract parameters from URI based on pattern."""
        params = {}
        if "{" in pattern:
            # Extract parameter name
            param_start = pattern.index("{")
            param_end = pattern.index("}")
            param_name = pattern[param_start + 1 : param_end]

            # Extract value from URI
            base_pattern = pattern[:param_start]
            if uri.startswith(base_pattern):
                param_value = uri[len(base_pattern) :]
                params[param_name] = param_value

        return params

    def run(self) -> None:
        """Run the HTTP/HTTPS server."""
        if self.ssl_config:
            # Run with SSL/TLS
            uvicorn.run(
                self.app, 
                host=self.host, 
                port=self.port,
                ssl_keyfile=self.ssl_config["key"],
                ssl_certfile=self.ssl_config["cert"],
            )
        else:
            # Run without SSL
            uvicorn.run(self.app, host=self.host, port=self.port)


def create_http_server(host: str = "127.0.0.1", port: int = 8080, ssl_config: dict[str, Any] | None = None) -> HTTPMCPServer:
    """Create and return an HTTP/HTTPS MCP server instance.

    Args:
        host: Host to bind to
        port: Port to bind to
        ssl_config: Optional SSL configuration with 'cert' and 'key' paths

    Returns:
        HTTPMCPServer instance
    """
    mcp_server = ZammadMCPServer()
    return HTTPMCPServer(mcp_server, host=host, port=port, ssl_config=ssl_config)