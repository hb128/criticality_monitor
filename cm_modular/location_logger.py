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