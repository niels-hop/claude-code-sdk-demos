"""Custom email tools for Claude Agent SDK"""
import aiosqlite
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any
import os

from config import DATABASE_PATH


async def search_inbox_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Search emails using Gmail query syntax (simplified database version)

    Args:
        args: Dictionary with 'gmailQuery' key

    Returns:
        Tool result with email search results
    """
    gmail_query = args.get("gmailQuery", "")

    print(f"\n[EmailTools] search_inbox called with query: {gmail_query}")

    try:
        # Open database connection
        async with aiosqlite.connect(str(DATABASE_PATH)) as db:
            # Parse Gmail query (simplified - just handle basic cases)
            query_parts = []
            params = []

            # Basic Gmail query parsing
            if "from:" in gmail_query:
                # Extract from: part
                import re
                from_match = re.search(r'from:(\S+)', gmail_query)
                if from_match:
                    from_addr = from_match.group(1)
                    query_parts.append("from_address LIKE ?")
                    params.append(f"%{from_addr}%")

            if "subject:" in gmail_query:
                import re
                subject_match = re.search(r'subject:(\S+)', gmail_query)
                if subject_match:
                    subject_text = subject_match.group(1)
                    query_parts.append("subject LIKE ?")
                    params.append(f"%{subject_text}%")

            if "to:" in gmail_query:
                import re
                to_match = re.search(r'to:(\S+)', gmail_query)
                if to_match:
                    to_addr = to_match.group(1)
                    # Need to join with recipients table
                    pass  # TODO: handle recipients

            # Build SQL query
            sql = """
                SELECT
                    e.message_id,
                    e.subject,
                    e.from_address,
                    e.from_name,
                    e.date_sent,
                    e.body_text,
                    e.snippet,
                    e.has_attachments,
                    e.is_read,
                    e.folder,
                    e.labels,
                    GROUP_CONCAT(CASE WHEN r.type = 'to' THEN r.address END) as to_addresses
                FROM emails e
                LEFT JOIN recipients r ON e.id = r.email_id
            """

            if query_parts:
                sql += " WHERE " + " AND ".join(query_parts)

            sql += " GROUP BY e.id ORDER BY e.date_sent DESC LIMIT 30"

            # Execute query
            cursor = await db.execute(sql, params)
            rows = await cursor.fetchall()

            # Format results
            emails = []
            for row in rows:
                email = {
                    "messageId": row[0],
                    "subject": row[1] or "",
                    "from": f"{row[3]} <{row[2]}>" if row[3] else row[2],
                    "to": row[11] or "",
                    "date": row[4],
                    "body": row[5] or row[6] or "",  # body_text or snippet
                    "hasAttachments": bool(row[7]),
                    "isRead": bool(row[8]),
                    "folder": row[9] or "INBOX",
                    "labels": json.loads(row[10]) if row[10] else []
                }
                emails.append(email)

            print(f"[EmailTools] Found {len(emails)} emails")

            # Save to log file (like TypeScript version)
            logs_dir = Path(__file__).parent.parent / "logs"
            logs_dir.mkdir(exist_ok=True)

            timestamp = datetime.now().isoformat().replace(":", "-").replace(".", "-")
            log_file = logs_dir / f"email-search-{timestamp}.json"

            log_data = {
                "query": gmail_query,
                "timestamp": datetime.now().isoformat(),
                "totalResults": len(emails),
                "ids": [e["messageId"] for e in emails],
                "emails": emails
            }

            with open(log_file, "w") as f:
                json.dump(log_data, f, indent=2)

            print(f"[EmailTools] Wrote results to {log_file}")

            return {
                "content": [{
                    "type": "text",
                    "text": json.dumps({
                        "totalResults": len(emails),
                        "logFilePath": str(log_file),
                        "message": f"Full email search results written to {log_file}"
                    }, indent=2)
                }]
            }

    except Exception as e:
        print(f"[EmailTools] Error in search_inbox: {e}")
        import traceback
        traceback.print_exc()
        return {
            "content": [{
                "type": "text",
                "text": f"Error searching inbox: {str(e)}"
            }]
        }


async def read_emails_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Read multiple emails by their message IDs

    Args:
        args: Dictionary with 'ids' key (list of message IDs)

    Returns:
        Tool result with email contents
    """
    ids = args.get("ids", [])

    print(f"\n[EmailTools] read_emails called with {len(ids)} IDs")

    try:
        async with aiosqlite.connect(str(DATABASE_PATH)) as db:
            # Build query with placeholders
            placeholders = ",".join("?" * len(ids))
            sql = f"""
                SELECT
                    e.message_id,
                    e.subject,
                    e.from_address,
                    e.from_name,
                    e.date_sent,
                    e.body_text,
                    e.snippet,
                    e.has_attachments,
                    e.is_read,
                    e.folder,
                    e.labels,
                    GROUP_CONCAT(CASE WHEN r.type = 'to' THEN r.address END) as to_addresses
                FROM emails e
                LEFT JOIN recipients r ON e.id = r.email_id
                WHERE e.message_id IN ({placeholders})
                GROUP BY e.id
                ORDER BY e.date_sent DESC
            """

            cursor = await db.execute(sql, ids)
            rows = await cursor.fetchall()

            # Format results
            emails = []
            for row in rows:
                email = {
                    "messageId": row[0],
                    "subject": row[1] or "",
                    "from": f"{row[3]} <{row[2]}>" if row[3] else row[2],
                    "to": row[11] or "",
                    "date": row[4],
                    "body": row[5] or row[6] or "",  # body_text or snippet
                    "hasAttachments": bool(row[7]),
                    "isRead": bool(row[8]),
                    "folder": row[9] or "INBOX",
                    "labels": json.loads(row[10]) if row[10] else []
                }
                emails.append(email)

            print(f"[EmailTools] Fetched {len(emails)} emails")

            return {
                "content": [{
                    "type": "text",
                    "text": json.dumps({
                        "totalFetched": len(emails),
                        "emails": emails
                    }, indent=2)
                }]
            }

    except Exception as e:
        print(f"[EmailTools] Error in read_emails: {e}")
        import traceback
        traceback.print_exc()
        return {
            "content": [{
                "type": "text",
                "text": f"Error reading emails: {str(e)}"
            }]
        }


def create_email_tools_server():
    """Create the MCP server with email tools"""
    try:
        from claude_agent_sdk import tool, create_sdk_mcp_server

        # Define tools
        search_tool = tool(
            "search_inbox",
            "Search emails in the inbox using Gmail query syntax",
            {"gmailQuery": str}
        )(search_inbox_tool)

        read_tool = tool(
            "read_emails",
            "Read multiple emails by their IDs to get full content and details",
            {"ids": list}  # List of email message IDs
        )(read_emails_tool)

        # Create MCP server
        server = create_sdk_mcp_server(
            name="email",
            version="1.0.0",
            tools=[search_tool, read_tool]
        )

        print("[EmailTools] Created email tools MCP server")
        return server

    except ImportError as e:
        print(f"[EmailTools] Warning: Could not import Claude Agent SDK: {e}")
        print("[EmailTools] Email tools will not be available")
        return None
    except Exception as e:
        print(f"[EmailTools] Error creating email tools server: {e}")
        import traceback
        traceback.print_exc()
        return None
