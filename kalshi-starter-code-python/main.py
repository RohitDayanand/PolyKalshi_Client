import os
from pathlib import Path
from dotenv import load_dotenv
from cryptography.hazmat.primitives import serialization
import asyncio

from kalshi_client import KalshiHttpClient, KalshiWebSocketClient, Environment

# Always load .env from the project root
env_path = Path(__file__).resolve().parents[1] / '.env'
load_dotenv(dotenv_path=env_path)

def main():
    """Example usage of the Kalshi API clients."""
    # Set up environment
    env = Environment.PROD
    key_id = os.getenv('PROD_KEYID')
    
    # Get the directory where the script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    keyfile = os.path.join(script_dir, 'kalshi_key_file.txt')
    
    try:
        # Load private key
        with open(keyfile, "rb") as key_file:
            private_key = serialization.load_pem_private_key(
                key_file.read(),
                password=None
            )
        
        # Initialize HTTP client
        http_client = KalshiHttpClient(
            key_id=key_id,
            private_key=private_key,
            environment=env
        )
        
        # Get account balance
        balance = http_client.get_balance()
        print("Balance:", balance)
        
        # Example of using WebSocket client
        print("\nTo use the WebSocket client, run orchestrate.py instead.")
        print("Example: python orchestrate.py")
        
    except FileNotFoundError:
        print(f"Private key file not found at {keyfile}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()

# Export the classes and environment enum
__all__ = ['KalshiWebSocketClient', 'Environment']
