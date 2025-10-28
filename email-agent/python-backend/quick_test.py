#!/usr/bin/env python3
"""Quick test to verify the fix"""
import asyncio
import json
import websockets


async def test():
    uri = "ws://127.0.0.1:3001/ws"
    async with websockets.connect(uri) as ws:
        # Receive welcome
        welcome = await ws.recv()
        print(f"✓ Connected: {json.loads(welcome)['type']}")

        # Send chat message
        await ws.send(json.dumps({
            "type": "chat",
            "content": "test",
            "sessionId": "quick-test"
        }))

        # Receive messages
        for i in range(3):
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
                data = json.loads(msg)
                print(f"✓ Received: {data['type']}")
                if 'error' in data:
                    error_msg = data['error']
                    if 'append_system_prompt' in error_msg:
                        print(f"✗ STILL HAS OLD ERROR!")
                        return False
                    else:
                        print(f"  Error (expected): {error_msg[:80]}")
                        return True
            except asyncio.TimeoutError:
                break

    return True


if __name__ == "__main__":
    result = asyncio.run(test())
    exit(0 if result else 1)
