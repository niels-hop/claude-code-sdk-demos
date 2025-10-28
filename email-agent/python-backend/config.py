import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from parent directory's .env
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# API Configuration
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '')

# Database Configuration
DATABASE_PATH = Path(__file__).parent.parent / 'emails.db'

# Server Configuration
PYTHON_BACKEND_PORT = int(os.getenv('PYTHON_BACKEND_PORT', '3001'))
PYTHON_BACKEND_HOST = os.getenv('PYTHON_BACKEND_HOST', '127.0.0.1')

# Agent Configuration
AGENT_DIR = Path(__file__).parent.parent / 'agent'
MAX_TURNS = 100
MODEL = "opus"
