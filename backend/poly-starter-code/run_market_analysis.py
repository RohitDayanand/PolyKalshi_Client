import subprocess
import json
import os
from typing import Tuple, Optional
import sys
print("Interpreter used:", sys.executable)


def get_user_input() -> str:
    """Get market slug from user input."""
    print("\nAvailable market slugs:")
    print("1. poland-presidential-election")
    print("2. romania-presidential-election")
    print("3. Enter custom slug")
    
    choice = input("\nEnter your choice (1-3): ").strip()
    
    if choice == "1":
        return "poland-presidential-election"
    elif choice == "2":
        return "romania-presidential-election"
    elif choice == "3":
        return input("Enter the market slug: ").strip()
    else:
        print("Invalid choice. Using default: poland-presidential-election")
        return "poland-presidential-election"

def read_generated_files(slug: str) -> Tuple[Optional[list], Optional[list]]:
    """Read the generated condition_id_list and token_ids_list files."""
    try:
        with open(f'{slug}_condition_id_list.json', 'r') as f:
            condition_ids = json.loads(f.read().strip())
        
        with open(f'{slug}_token_ids_list.json', 'r') as f:
            token_ids = json.loads(f.read().strip())
            
        return condition_ids, token_ids
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error reading generated files: {e}")
        return None, None

def main():
    # Change to the script's directory to ensure consistent paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    # Get user input for market slug
    slug = get_user_input()
    print(f"\nSelected market slug: {slug}")
    
    # Step 1: Run Market_Finder.py
    print("\nStep 1: Running Market_Finder.py...")
    try:
        subprocess.run([sys.executable, 'Market_Finder.py', slug], check=True)
        print("Market_Finder.py completed successfully")
    except subprocess.CalledProcessError as e:
        print(f"Error running Market_Finder.py: {e}")
        return
    
    # Step 2: Run connection.py
    print("\nStep 2: Running connection.py...")
    try:
        subprocess.run([sys.executable, 'connection.py', slug], check=True)
        print("connection.py completed successfully")
    except subprocess.CalledProcessError as e:
        print(f"Error running connection.py: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")

if __name__ == "__main__":
    main()