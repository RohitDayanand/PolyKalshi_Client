from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[1]
KALSHI_KEY_PATH = PROJECT_ROOT /  os.getenv("KALSHI_KEY_PATH") 
#this should be the relative to path to RSA text file provided by Kalshi. 
# MAKE SURE it is inside the project root, and that the path is relative like backend/kalshi_key_file.txt

