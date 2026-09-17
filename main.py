import sys
from pathlib import Path

# Ensure root directory is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from desktop_launcher import main

if __name__ == "__main__":
    main()
