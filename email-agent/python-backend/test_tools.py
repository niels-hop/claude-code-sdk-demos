#!/usr/bin/env python3
"""Test custom email tools directly (without SDK)"""
import asyncio
import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from custom_tools import search_inbox_tool, read_emails_tool


async def test_search_inbox():
    """Test search_inbox tool"""
    print("\n=== Testing search_inbox_tool ===")

    # Test with empty query (should return recent emails)
    result = await search_inbox_tool({"gmailQuery": ""})

    print(f"✓ search_inbox_tool executed")
    content = result.get("content", [])
    if content:
        import json
        data = json.loads(content[0]["text"])
        print(f"  Total results: {data.get('totalResults', 0)}")
        print(f"  Log file: {data.get('logFilePath', 'N/A')}")
        return data.get('totalResults', 0) > 0
    return False


async def test_read_emails():
    """Test read_emails tool"""
    print("\n=== Testing read_emails_tool ===")

    # First, search for some emails to get IDs
    search_result = await search_inbox_tool({"gmailQuery": ""})
    content = search_result.get("content", [])

    if not content:
        print("✗ No search results to test with")
        return False

    import json
    search_data = json.loads(content[0]["text"])

    # Read the log file to get email IDs
    import pathlib
    log_file = pathlib.Path(search_data.get("logFilePath", ""))

    if not log_file.exists():
        print("✗ Log file not found")
        return False

    with open(log_file) as f:
        log_data = json.load(f)

    ids = log_data.get("ids", [])[:3]  # Get first 3 IDs

    if not ids:
        print("✗ No email IDs found")
        return False

    print(f"  Testing with {len(ids)} email IDs")

    # Test read_emails
    result = await read_emails_tool({"ids": ids})

    print(f"✓ read_emails_tool executed")
    content = result.get("content", [])
    if content:
        data = json.loads(content[0]["text"])
        print(f"  Total fetched: {data.get('totalFetched', 0)}")
        return data.get('totalFetched', 0) > 0

    return False


async def test_database_exists():
    """Test if database exists and has emails"""
    print("\n=== Testing Database ===")

    from config import DATABASE_PATH
    import aiosqlite

    if not DATABASE_PATH.exists():
        print(f"✗ Database not found at {DATABASE_PATH}")
        return False

    print(f"✓ Database exists: {DATABASE_PATH}")

    try:
        async with aiosqlite.connect(str(DATABASE_PATH)) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM emails")
            row = await cursor.fetchone()
            count = row[0] if row else 0

            print(f"  Total emails in database: {count}")
            return count > 0

    except Exception as e:
        print(f"✗ Database error: {e}")
        return False


async def run_all_tests():
    """Run all tool tests"""
    print("=" * 60)
    print("Email Tools Test Suite")
    print("=" * 60)

    results = []

    # Test 1: Database
    results.append(await test_database_exists())

    # Test 2: Search tool
    results.append(await test_search_inbox())

    # Test 3: Read tool
    results.append(await test_read_emails())

    # Summary
    print("\n" + "=" * 60)
    print(f"Test Results: {sum(results)}/{len(results)} passed")
    print("=" * 60)

    if all(results):
        print("\n✓ All custom tools are working correctly!")
        print("\nNext: These tools will be available to Claude SDK as:")
        print("  - mcp__email__search_inbox")
        print("  - mcp__email__read_emails")
        return 0
    else:
        print("\n✗ Some tests failed.")
        if not results[0]:
            print("  → Database not found or empty. Run email sync first.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_all_tests())
    sys.exit(exit_code)
