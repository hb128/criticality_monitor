#!/usr/bin/env python3
"""
Simple health check script for Docker containers.
"""

import sys
import os
from pathlib import Path


def check_health():
    """Perform basic health checks."""
    
    # Check if we can import required modules
    try:
        import pandas as pd
        import folium
        # Add other critical imports
    except ImportError as e:
        print(f"Import error: {e}")
        return False
    
    # Check if critical directories exist
    required_dirs = [
        "/app/cm_logs",
        "/app/site",
        "/app/config"
    ]
    
    for dir_path in required_dirs:
        if not Path(dir_path).exists():
            print(f"Missing directory: {dir_path}")
            return False
    
    return True


if __name__ == "__main__":
    if check_health():
        print("Health check passed")
        sys.exit(0)
    else:
        print("Health check failed")
        sys.exit(1)