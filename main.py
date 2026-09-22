"""
GPT-to-WeChat main entry point.
"""

import sys
from cli import main

if __name__ == "__main__":
    if len(sys.argv) == 1:
        # Default to launching Web UI if no arguments provided
        sys.argv.append("ui")
    main()
