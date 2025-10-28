from typing import AsyncIterator, Optional, Dict, Any
import asyncio
from config import ANTHROPIC_API_KEY, AGENT_DIR, MAX_TURNS, MODEL


class ClaudeClient:
    """Wrapper for Claude Agent SDK"""

    def __init__(self, custom_tools_server=None):
        self.custom_tools_server = custom_tools_server
        self.email_agent_prompt = self._load_email_agent_prompt()

    def _load_email_agent_prompt(self) -> str:
        """Load the email agent system prompt"""
        # We'll implement this to load from the TypeScript file later
        return """You are an email assistant. You can help users search and read their emails.

Available tools:
- search_inbox: Search emails using Gmail query syntax
- read_emails: Read full content of emails by their IDs

Be concise and helpful."""

    async def query_stream(
        self,
        prompt: str,
        session_id: Optional[str] = None,
        resume_session_id: Optional[str] = None
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Stream a query to Claude and yield messages

        Args:
            prompt: The user's message
            session_id: Internal session ID (for our tracking)
            resume_session_id: SDK session ID to resume conversation
        """
        try:
            # Import here to avoid issues if SDK not installed during development
            from claude_agent_sdk import query, ClaudeAgentOptions

            print(f"\n[ClaudeClient] Starting query...")
            print(f"  Prompt: {prompt[:100]}...")
            print(f"  Resume: {resume_session_id}")

            # Prepare options
            options_dict = {
                "max_turns": MAX_TURNS,
                "cwd": str(AGENT_DIR),
                "model": MODEL,
                "allowed_tools": [
                    "Task", "Bash", "Glob", "Grep", "Read", "Edit", "Write",
                    "mcp__email__search_inbox",
                    "mcp__email__read_emails"
                ],
                "system_prompt": self.email_agent_prompt,
            }

            # Add MCP servers if available
            if self.custom_tools_server:
                options_dict["mcp_servers"] = {
                    "email": self.custom_tools_server
                }

            # Add resume option if provided
            if resume_session_id:
                options_dict["resume"] = resume_session_id

            options = ClaudeAgentOptions(**options_dict)

            # Stream messages from Claude
            async for message in query(prompt=prompt, options=options):
                print(f"[ClaudeClient] Message type: {message.get('type', 'unknown')}")
                yield message

        except ImportError as e:
            print(f"[ClaudeClient] SDK Import Error: {e}")
            yield {
                "type": "error",
                "error": "Claude Agent SDK not properly installed",
                "details": str(e)
            }
        except Exception as e:
            print(f"[ClaudeClient] Error: {e}")
            yield {
                "type": "error",
                "error": str(e),
                "error_type": type(e).__name__
            }
