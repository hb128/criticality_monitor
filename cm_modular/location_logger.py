"""
Location Logger Module

This module provides functionality to log locations from the Criticality Monitor API
and create interactive maps with the logged position data.
"""

import requests
import json
import numpy as np
import datetime
import os


def load_locations() -> dict:
    """
    Load location data from the Criticality Monitor API.
    
    Returns:
        dict: JSON response containing location data
        
    Raises:
        requests.RequestException: If API request fails
    """
    baseurl = 'https://api.criticalmaps.net/'
    r = requests.post(baseurl)
    print(f"API Response: {r.status_code}, Headers: {r.headers}")
    jp = json.loads(r.text)
    print(f"Response data: {r.text}")
    return jp

def log_locations(log_path: str) -> dict:
    """
    Log current locations to a file and return position coordinates.
    
    Args:
        log_path (str): Directory path to save log files
        
    Returns:
        dict: Dictionary containing [latitude, longitude] coordinates

    Raises:
        requests.RequestException: If API request fails
        OSError: If file writing fails
    """
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    locations = load_locations()
    
    # Ensure log directory exists
    os.makedirs(log_path, exist_ok=True)
    
    # Save raw location data
    log_file = os.path.join(log_path, f"{timestamp}.txt")
    with open(log_file, 'w') as file:
        file.write(json.dumps(locations, indent=2))

    return locations