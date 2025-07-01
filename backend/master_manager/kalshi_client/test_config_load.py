#print(__package__)

from .kalshi_client_config import KalshiClientConfig

def test_default_config_load():
    try:
        config = KalshiClientConfig(ticker="TEST_TICKER")
        assert config.private_key is not None
        print("✅ Private key loaded successfully from default path.")
        print(f"Key ID: {config.key_id}")
        print(f"Private key path: {config.private_key_path}")
    except Exception as e:
        print(f"❌ Failed to load private key: {e}")

if __name__ == "__main__":
    test_default_config_load()
