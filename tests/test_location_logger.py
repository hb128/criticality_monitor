from unittest.mock import patch, Mock
import json
from cm_modular.location_logger import load_locations

def test_load_locations_parses_api_response():
    # Create mock response
    mock_json_data = {
        "locations": [
            {"latitude": 53.55, "longitude": 10.0, "timestamp": 1234567890},
            {"latitude": 53.56, "longitude": 10.01, "timestamp": 1234567900}
        ]
    }
    
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.text = json.dumps(mock_json_data)
    mock_response.headers = {"content-type": "application/json"}
    
    with patch('cm_modular.location_logger.requests.post', return_value=mock_response):
        result = load_locations()
        
        assert result == mock_json_data
        assert len(result["locations"]) == 2
        assert result["locations"][0]["latitude"] == 53.55