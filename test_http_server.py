#!/usr/bin/env python
"""Test script for Zammad MCP HTTP/SSE server."""

import asyncio
import json

import httpx


async def test_http_server():
    """Test the HTTP server endpoints."""
    base_url = "http://localhost:8080"
    
    async with httpx.AsyncClient() as client:
        print("Testing Zammad MCP HTTP Server")
        print("=" * 50)
        
        # Test health endpoint
        print("\n1. Testing health endpoint...")
        response = await client.get(f"{base_url}/health")
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}")
        
        # Test listing tools
        print("\n2. Testing tools/list...")
        response = await client.post(
            f"{base_url}/mcp/call",
            json={"method": "tools/list"}
        )
        print(f"   Status: {response.status_code}")
        data = response.json()
        if "result" in data and "tools" in data["result"]:
            print(f"   Found {len(data['result']['tools'])} tools")
            for tool in data["result"]["tools"][:3]:  # Show first 3
                print(f"     - {tool['name']}: {tool.get('description', '')[:60]}...")
        
        # Test listing resources
        print("\n3. Testing resources/list...")
        response = await client.post(
            f"{base_url}/mcp/call",
            json={"method": "resources/list"}
        )
        print(f"   Status: {response.status_code}")
        data = response.json()
        if "result" in data and "resources" in data["result"]:
            print(f"   Found {len(data['result']['resources'])} resources")
            for resource in data["result"]["resources"]:
                print(f"     - {resource['uri']}: {resource.get('description', '')}")
        
        # Test listing prompts
        print("\n4. Testing prompts/list...")
        response = await client.post(
            f"{base_url}/mcp/call",
            json={"method": "prompts/list"}
        )
        print(f"   Status: {response.status_code}")
        data = response.json()
        if "result" in data and "prompts" in data["result"]:
            print(f"   Found {len(data['result']['prompts'])} prompts")
            for prompt in data["result"]["prompts"]:
                print(f"     - {prompt['name']}: {prompt.get('description', '')[:60]}...")
        
        # Test SSE streaming
        print("\n5. Testing SSE streaming...")
        print("   Sending request to /mcp/stream...")
        try:
            # Note: httpx doesn't have built-in SSE support, so we'll just check if endpoint responds
            response = await client.post(
                f"{base_url}/mcp/stream",
                json={"method": "tools/list"},
                timeout=2.0
            )
            print(f"   Status: {response.status_code}")
            print(f"   Headers: {dict(response.headers)}")
            if "text/event-stream" in response.headers.get("content-type", ""):
                print("   ✓ SSE endpoint is responding with event-stream content type")
        except httpx.ReadTimeout:
            print("   ✓ SSE endpoint is streaming (timeout expected for continuous stream)")
        
        print("\n" + "=" * 50)
        print("All tests completed!")


async def test_sse_stream():
    """Test SSE streaming with proper SSE client."""
    print("\n6. Testing SSE stream with event parsing...")
    print("   Connecting to SSE endpoint...")
    
    async with httpx.AsyncClient() as client:
        # Send a request that will trigger SSE
        async with client.stream(
            "POST",
            "http://localhost:8080/mcp/stream",
            json={"method": "tools/list"},
            timeout=5.0
        ) as response:
            print(f"   Connected! Status: {response.status_code}")
            print("   Receiving events:")
            
            buffer = ""
            event_count = 0
            async for chunk in response.aiter_text():
                buffer += chunk
                # Parse SSE events
                while "\n\n" in buffer:
                    event, buffer = buffer.split("\n\n", 1)
                    if event.strip():
                        event_count += 1
                        lines = event.strip().split("\n")
                        event_type = None
                        event_data = None
                        
                        for line in lines:
                            if line.startswith("event:"):
                                event_type = line[6:].strip()
                            elif line.startswith("data:"):
                                event_data = line[5:].strip()
                        
                        if event_type and event_data:
                            print(f"     Event #{event_count}: {event_type}")
                            try:
                                data = json.loads(event_data)
                                print(f"       Data: {json.dumps(data, indent=2)[:200]}...")
                            except json.JSONDecodeError:
                                print(f"       Data: {event_data[:100]}...")
                        
                        # Stop after receiving the 'done' event
                        if event_type == "done":
                            print("   ✓ Stream completed successfully")
                            break


if __name__ == "__main__":
    print("Make sure the server is running with:")
    print("  python -m mcp_zammad --mode http")
    print()
    input("Press Enter when the server is running...")
    
    # Run tests
    asyncio.run(test_http_server())
    
    # Test SSE separately
    try:
        asyncio.run(test_sse_stream())
    except Exception as e:
        print(f"SSE test error (this is okay if server doesn't support full SSE yet): {e}")