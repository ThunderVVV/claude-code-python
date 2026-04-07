#!/usr/bin/env python3
"""
API Connection Diagnostic Tool

This script tests the connection to the configured API endpoint
to help diagnose connection issues.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
import httpx


async def test_api_connection():
    """Test the API connection and report issues."""
    # Load environment variables
    load_dotenv()

    api_url = os.environ.get("CLAUDE_CODE_API_URL")
    api_key = os.environ.get("CLAUDE_CODE_API_KEY")
    model = os.environ.get("CLAUDE_CODE_MODEL")

    print("=" * 60)
    print("  Claude Code Python - API Connection Diagnostic")
    print("=" * 60)
    print()

    # Check configuration
    print("Configuration Check:")
    print(f"  API URL: {api_url or 'NOT SET'}")
    print(f"  API Key: {'***' + api_key[-4:] if api_key and len(api_key) > 4 else 'NOT SET'}")
    print(f"  Model: {model or 'NOT SET'}")
    print()

    if not api_url or not api_key or not model:
        print("ERROR: Missing configuration!")
        print("Please set CLAUDE_CODE_API_URL, CLAUDE_CODE_API_KEY, and CLAUDE_CODE_MODEL")
        print("in your .env file or environment variables.")
        return False

    # Normalize API URL
    if api_url.endswith("/chat/completions"):
        api_url = api_url.rsplit("/chat/completions", 1)[0]
    elif api_url.endswith("/v1/chat/completions"):
        api_url = api_url.rsplit("/v1/chat/completions", 1)[0] + "/v1"

    print(f"  Normalized URL: {api_url}")
    print()

    # Test 1: DNS resolution
    print("Test 1: DNS Resolution...")
    try:
        from urllib.parse import urlparse
        parsed = urlparse(api_url)
        hostname = parsed.hostname
        print(f"  Hostname: {hostname}")

        import socket
        ip = socket.gethostbyname(hostname)
        print(f"  Resolved IP: {ip}")
        print("  ✓ DNS resolution successful")
    except Exception as e:
        print(f"  ✗ DNS resolution failed: {e}")
        return False
    print()

    # Test 2: TCP connection
    print("Test 2: TCP Connection...")
    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(hostname, port),
            timeout=10.0
        )
        writer.close()
        await writer.wait_closed()
        print(f"  ✓ TCP connection to {hostname}:{port} successful")
    except asyncio.TimeoutError:
        print(f"  ✗ TCP connection timed out")
        return False
    except Exception as e:
        print(f"  ✗ TCP connection failed: {e}")
        return False
    print()

    # Test 3: HTTP request
    print("Test 3: HTTP Request...")
    try:
        async with httpx.AsyncClient(
            http2=True,  # Enable HTTP/2 support
            timeout=httpx.Timeout(connect=30.0, read=60.0, write=60.0, pool=30.0),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        ) as client:
            # Try to list models or make a simple request
            try:
                response = await client.get(f"{api_url}/models")
                print(f"  Models endpoint status: HTTP {response.status_code}")
                if response.status_code == 200:
                    print("  ✓ Models endpoint accessible")
                elif response.status_code == 401:
                    print("  ✗ Authentication failed - check your API key")
                    return False
                elif response.status_code == 404:
                    print("  ! Models endpoint not found (this may be normal for some APIs)")
            except Exception as e:
                print(f"  ! Models request failed: {e}")
    except Exception as e:
        print(f"  ✗ HTTP client error: {e}")
        return False
    print()

    # Test 4: Chat completion request
    print("Test 4: Chat Completion Request...")
    try:
        async with httpx.AsyncClient(
            base_url=api_url,
            http2=True,  # Enable HTTP/2 support
            timeout=httpx.Timeout(connect=30.0, read=120.0, write=60.0, pool=30.0),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        ) as client:
            request_data = {
                "model": model,
                "messages": [{"role": "user", "content": "Say 'Hello'"}],
                "max_tokens": 10,
            }

            print(f"  Sending request to {api_url}/chat/completions...")
            response = await client.post("/chat/completions", json=request_data)

            if response.status_code == 200:
                data = response.json()
                print("  ✓ Chat completion successful!")
                if "choices" in data and data["choices"]:
                    msg = data["choices"][0].get("message", {})
                    content = msg.get("content") if msg else None
                    if content:
                        print(f"  Response: {content[:100]}...")
                    else:
                        print("  Response: (no text content)")
                return True
            else:
                print(f"  ✗ Request failed with HTTP {response.status_code}")
                print(f"  Response: {response.text[:500]}")
                return False

    except httpx.ConnectError as e:
        print(f"  ✗ Connection error: {e}")
        print("  This usually means:")
        print("    - The server is not reachable")
        print("    - A firewall is blocking the connection")
        print("    - The API URL is incorrect")
        return False
    except httpx.ConnectTimeout as e:
        print(f"  ✗ Connection timeout: {e}")
        print("  The server took too long to respond")
        return False
    except httpx.ReadTimeout as e:
        print(f"  ✗ Read timeout: {e}")
        print("  The server accepted the connection but didn't respond in time")
        return False
    except httpx.RemoteProtocolError as e:
        print(f"  ✗ Protocol error: {e}")
        print("  The server closed the connection unexpectedly")
        print("  This could be due to:")
        print("    - Server overload")
        print("    - Invalid API key")
        print("    - Rate limiting")
        print("    - Request too large")
        return False
    except Exception as e:
        print(f"  ✗ Request failed: {type(e).__name__}: {e}")
        return False


def main():
    try:
        success = asyncio.run(test_api_connection())
        print()
        print("=" * 60)
        if success:
            print("  ✓ All tests passed! Your API connection is working.")
        else:
            print("  ✗ Some tests failed. Please check the errors above.")
        print("=" * 60)
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        sys.exit(130)


if __name__ == "__main__":
    main()
