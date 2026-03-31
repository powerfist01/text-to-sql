"""
config.py
---------
Central place for all environment variables.
Import this in any file that needs config values.

Usage:
    from config import ANTHROPIC_API_KEY, MODEL
"""

import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
VOYAGE_API_KEY = os.getenv("VOYAGE_API_KEY")
MODEL = "claude-haiku-4-5"

if not ANTHROPIC_API_KEY:
    raise ValueError("ANTHROPIC_API_KEY not found. Make sure it is set in your .env file.")

if not VOYAGE_API_KEY:
    raise ValueError("VOYAGE_API_KEY not found. Make sure it is set in your .env file.")
