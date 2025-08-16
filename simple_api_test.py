"""
Simple API Response Format Test

This script makes direct HTTP requests to test API endpoints for standardized response format.
"""

import requests
import json
import sys

# Base URL for API
BASE_URL = "http://localhost:8000/api/"

# Expected fields in standardized response
EXPECTED_FIELDS = ['count', 'next', 'previous', 'results']

def print_header(text):
    print("\n" + "=" * 50)
    print(text)
    print("=" * 50)

def print_success(text):
    print(f"✓ {text}")

def print_error(text):
    print(f"✗ {text}")

def print_warning(text):
    print(f"! {text}")

def get_auth_token():
    """Get authentication token for API requests"""
    auth_url = BASE_URL + "token/"
    
    # Replace with valid credentials
    credentials = {
        'username': 'admin',  # Replace with a valid username
        'password': 'admin'   # Replace with a valid password
    }
    
    try:
        response = requests.post(auth_url, data=credentials)
        if response.status_code == 200:
            token_data = response.json()
            return token_data.get('access')
        else:
            print_error(f"Authentication failed: {response.status_code}")
            print(response.text)
            return None
    except Exception as e:
        print_error(f"Error getting auth token: {str(e)}")
        return None

def check_response_format(response_data):
    """Check if response data follows the standardized format"""
    missing_fields = [field for field in EXPECTED_FIELDS if field not in response_data]
    
    if missing_fields:
        print_error(f"Missing fields: {', '.join(missing_fields)}")
        return False
    
    if not isinstance(response_data['results'], list):
        print_error("'results' field is not a list")
        return False
    
    print_success("Response format is correct")
    print(f"  Count: {response_data['count']}")
    print(f"  Results items: {len(response_data['results'])}")
    return True

def test_endpoint(url, token=None, method='GET', data=None):
    """Test a specific endpoint for standardized response format"""
    full_url = BASE_URL + url
    print(f"\nTesting endpoint: {full_url}")
    print("-" * 30)
    
    headers = {}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    
    try:
        # Make the request
        if method.upper() == 'GET':
            response = requests.get(full_url, headers=headers)
        elif method.upper() == 'POST':
            response = requests.post(full_url, json=data, headers=headers)
        else:
            print_error(f"Unsupported method: {method}")
            return False
        
        # Check if response is successful
        if response.status_code >= 400:
            print_error(f"Request failed with status code: {response.status_code}")
            print(response.text)
            return False
        
        # Parse response content
        try:
            response_data = response.json()
        except json.JSONDecodeError:
            print_error("Response is not valid JSON")
            print(response.text)
            return False
        
        # Check response format
        return check_response_format(response_data)
    
    except Exception as e:
        print_error(f"Error testing endpoint: {str(e)}")
        return False

def main():
    """Main function to test key endpoints"""
    print_header("Simple API Response Format Test")
    
    # Get authentication token
    token = get_auth_token()
    if not token:
        print_warning("Proceeding without authentication token. Some tests may fail.")
    
    # Test endpoints
    endpoints = [
        # Documents endpoints
        {'url': 'documents/', 'method': 'GET'},
        {'url': 'documents/stats/', 'method': 'GET'},
        
        # Departments endpoints
        {'url': 'departments/', 'method': 'GET'},
        
        # Users endpoints
        {'url': 'users/', 'method': 'GET'},
        {'url': 'auth/user/', 'method': 'GET'},
        
        # Auth endpoints
        {'url': 'auth/logout/', 'method': 'POST', 'data': {}},
    ]
    
    results = {'passed': 0, 'failed': 0, 'total': len(endpoints), 'skipped': 0}
    
    for endpoint in endpoints:
        results['total'] += 1
        
        # Skip certain endpoints if no token
        if not token and endpoint['url'] != 'token/':
            print_warning(f"Skipping {endpoint['url']} - requires authentication")
            results['skipped'] += 1
            continue
        
        if test_endpoint(endpoint['url'], token, endpoint.get('method', 'GET'), endpoint.get('data')):
            results['passed'] += 1
        else:
            results['failed'] += 1
    
    # Print summary
    print_header("TEST SUMMARY")
    print(f"Total tests: {results['total']}")
    print(f"Passed: {results['passed']}")
    print(f"Failed: {results['failed']}")
    if results['skipped'] > 0:
        print(f"Skipped: {results['skipped']}")
    
    if results['failed'] == 0 and results['skipped'] == 0:
        print_success("\nAll endpoints are using the standardized response format!")
    elif results['failed'] == 0:
        print_warning("\nAll tested endpoints are using the standardized response format.")
        print("Some endpoints were skipped due to authentication requirements.")
    else:
        print_warning("\nSome endpoints are not using the standardized response format.")
        print("Please check the failed tests and update the corresponding views.")

if __name__ == "__main__":
    main()
