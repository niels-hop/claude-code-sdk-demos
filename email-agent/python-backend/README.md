# Email Agent Python Backend

Python backend service using Claude Agent SDK (Python) for the email-agent demo.

## Setup

1. Install Python 3.10 or higher

2. Create virtual environment:
```bash
cd python-backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Ensure `.env` file exists in parent directory with:
```
ANTHROPIC_API_KEY=your-key-here
```

## Running

From the `python-backend` directory:

```bash
# Activate virtual environment
source venv/bin/activate

# Run the server
python main.py
```

Server will start on `http://127.0.0.1:3001`

## Endpoints

- `GET /` - Health check
- `GET /health` - Detailed health status
- `WS /ws` - WebSocket endpoint for chat communication

## Architecture

```
main.py              - FastAPI app + WebSocket handler
session_manager.py   - Session and subscription management
claude_client.py     - Claude Agent SDK wrapper
custom_tools.py      - Email search/read tools (Step 2)
config.py           - Configuration and environment variables
```

## Testing

Test health endpoint:
```bash
curl http://127.0.0.1:3001/health
```

Test WebSocket (using websocat or similar):
```bash
websocat ws://127.0.0.1:3001/ws
```
