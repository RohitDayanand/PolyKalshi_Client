from paths import KALSHI_KEY_PATH

print("Resolved KALSHI_KEY_PATH:")
print(KALSHI_KEY_PATH)

# Optional: check if the file actually exists
if KALSHI_KEY_PATH.exists():
    print("✅ File exists!")
else:
    print("❌ File does NOT exist.")
