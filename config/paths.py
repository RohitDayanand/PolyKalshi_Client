from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[1]
KALSHI_KEY_PATH = PROJECT_ROOT /  "backend/master_manager/keys/kalshi_key_file.txt"
