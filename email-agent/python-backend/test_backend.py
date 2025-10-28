#!/usr/bin/env python3
"""
Test script for Python backend
Tests basic connectivity without requiring Anthropic API key
"""
import asyncio
import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    import websockets
    import aiohttp
except ImportError:
    print("Installing test dependencies...")
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "websockets", "aiohttp"])
    import websockets
    import aiohttp


async def test_health_endpoint():
    """Test HTTP health endpoint"""
    print("\n=== Testing Health Endpoint ===")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('http://127.0.0.1:3001/health') as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✓ Health endpoint working")
                    print(f"  Status: {data.get('status')}")
                    print(f"  Active sessions: {len(data.get('sessions', []))}")
                    return True
                else:
                    print(f"✗ Health endpoint returned status {response.status}")
                    return False
    except Exception as e:
        print(f"✗ Health endpoint failed: {e}")
        return False


async def test_websocket_connection():
    """Test WebSocket connection and basic message flow"""
    print("\n=== Testing WebSocket Connection ===")
    try:
        uri = "ws://127.0.0.1:3001/ws"
        async with websockets.connect(uri) as websocket:
            print("✓ WebSocket connected")

            # Receive welcome message
            welcome_msg = await websocket.recv()
            welcome_data = json.loads(welcome_msg)
            print(f"✓ Received welcome: {welcome_data.get('type')}")

            # Send a test chat message
            test_message = {
                "type": "chat",
                "content": "Hello, this is a test message",
                "sessionId": "test-session-123",
                "newConversation": False
            }
            await websocket.send(json.dumps(test_message))
            print("✓ Sent test chat message")

            # Receive messages for a few seconds
            print("\n  Waiting for responses (expecting API error without key)...")
            try:
                for i in range(5):  # Try to receive up to 5 messages
                    msg = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    data = json.loads(msg)
                    msg_type = data.get('type')
                    print(f"  → Received: {msg_type}", end="")

                    if msg_type == 'error':
                        print(f" - {data.get('error', '')[:80]}")
                        print("\n✓ Got expected error (no API key configured)")
                        return True
                    elif msg_type == 'user_message':
                        print(f" - echo: {data.get('content', '')[:50]}")
                    else:
                        print()

            except asyncio.TimeoutError:
                print("\n✓ No more messages (timeout)")

            return True

    except Exception as e:
        print(f"✗ WebSocket test failed: {e}")
        return False


async def test_session_management():
    """Test session creation and management"""
    print("\n=== Testing Session Management ===")
    try:
        uri = "ws://127.0.0.1:3001/ws"
        async with websockets.connect(uri) as ws1:
            # Create session
            await ws1.recv()  # Welcome message

            subscribe_msg = {
                "type": "subscribe",
                "sessionId": "test-multi-123"
            }
            await ws1.send(json.dumps(subscribe_msg))

            response = await ws1.recv()
            data = json.loads(response)
            if data.get('type') == 'subscribed':
                print("✓ Session subscription working")
                return True
            else:
                print(f"✗ Unexpected response: {data}")
                return False

    except Exception as e:
        print(f"✗ Session management test failed: {e}")
        return False


async def run_all_tests():
    """Run all tests"""
    print("=" * 60)
    print("Email Agent Python Backend - Test Suite")
    print("=" * 60)

    print("\nNOTE: Server must be running on port 3001")
    print("Start server with: python main.py\n")

    await asyncio.sleep(1)  # Give user time to read

    results = []

    # Test 1: Health endpoint
    results.append(await test_health_endpoint())

    # Test 2: WebSocket
    results.append(await test_websocket_connection())

    # Test 3: Session management
    results.append(await test_session_management())

    # Summary
    print("\n" + "=" * 60)
    print(f"Test Results: {sum(results)}/{len(results)} passed")
    print("=" * 60)

    if all(results):
        print("\n✓ All tests passed! Python backend is working correctly.")
        print("\nNext steps:")
        print("  1. The backend receives messages from WebSocket")
        print("  2. It echoes user messages back")
        print("  3. It attempts to call Claude SDK (will fail without API key)")
        print("  4. Error messages are properly returned")
        return 0
    else:
        print("\n✗ Some tests failed. Check server logs.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_all_tests())
    sys.exit(exit_code)
