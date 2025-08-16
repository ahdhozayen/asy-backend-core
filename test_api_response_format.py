"""
API Response Format Test Script

This script tests the consistency of API response formats across different endpoints
to ensure they all follow the standardized format with count, next, previous, and results fields.
"""

import os
import sys
import json
import requests
from pprint import pprint
from urllib.parse import urljoin

# Add the Django project to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ASY_CORE.settings')

# Base URL for API requests
BASE_URL = 'http://localhost:8000/api/'

# Endpoints to test
ENDPOINTS = {
    'documents': {
        'list': 'documents/',
        'detail': 'documents/1/',
        'stats': 'documents/stats/',
    },
    'departments': {
        'list': 'departments/',
        'detail': 'departments/1/',
    },
    'users': {
        'list': 'users/',
        'detail': 'users/1/',
        'profile': 'auth/user/',
    },
    'auth': {
        'logout': 'auth/logout/',
        'change_password': 'auth/change-password/',
    }
}

# Expected fields in standardized response
EXPECTED_FIELDS = ['count', 'next', 'previous', 'results']

# Colors for terminal output - with Windows compatibility
import os
import platform

class Colors:
    # Check if we're on Windows and not in a modern terminal that supports ANSI
    if platform.system() == 'Windows' and not os.environ.get('WT_SESSION'):
        HEADER = ''
        OKBLUE = ''
        OKGREEN = ''
        WARNING = ''
        FAIL = ''
        ENDC = ''
        BOLD = ''
        UNDERLINE = ''
    else:
        HEADER = '\033[95m'
        OKBLUE = '\033[94m'
        OKGREEN = '\033[92m'
        WARNING = '\033[93m'
        FAIL = '\033[91m'
        ENDC = '\033[0m'
        BOLD = '\033[1m'
        UNDERLINE = '\033[4m'


def get_auth_token():
    """Get authentication token for API requests"""
    auth_url = urljoin(BASE_URL, 'token')
    
    # Replace with valid credentials
    credentials = {
        'username': 'admin',  # Replace with a valid username
        'password': 'admin'   # Replace with a valid password
    }
    
    try:
        response = requests.post(auth_url, data=credentials)
        if response.status_code == 200:
            return response.json().get('access')
        else:
            print(f"{Colors.FAIL}Failed to get auth token: {response.status_code}{Colors.ENDC}")
            print(response.text)
            return None
    except Exception as e:
        print(f"{Colors.FAIL}Error getting auth token: {str(e)}{Colors.ENDC}")
        return None


def test_endpoint(url, token=None, method='GET', data=None):
    """Test a specific endpoint for standardized response format"""
    headers = {}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    
    full_url = urljoin(BASE_URL, url)
    print(f"{Colors.HEADER}Testing endpoint: {full_url}{Colors.ENDC}")
    
    try:
        if method.upper() == 'GET':
            response = requests.get(full_url, headers=headers)
        elif method.upper() == 'POST':
            response = requests.post(full_url, json=data, headers=headers)
        elif method.upper() == 'PUT':
            response = requests.put(full_url, json=data, headers=headers)
        elif method.upper() == 'PATCH':
            response = requests.patch(full_url, json=data, headers=headers)
        else:
            print(f"{Colors.FAIL}Unsupported method: {method}{Colors.ENDC}")
            return False
        
        # Check if response is JSON
        try:
            response_data = response.json()
        except json.JSONDecodeError:
            print(f"{Colors.FAIL}Response is not valid JSON{Colors.ENDC}")
            print(response.text)
            return False
        
        # Check for expected fields
        missing_fields = [field for field in EXPECTED_FIELDS if field not in response_data]
        
        if missing_fields:
            print(f"{Colors.FAIL}Missing fields: {', '.join(missing_fields)}{Colors.ENDC}")
            print("Response data:")
            pprint(response_data)
            return False
        else:
            print(f"{Colors.OKGREEN}✓ Response format is correct{Colors.ENDC}")
            
            # Check if results is a list
            if not isinstance(response_data['results'], list):
                print(f"{Colors.WARNING}Warning: 'results' field is not a list{Colors.ENDC}")
            
            # Print response summary
            print(f"  Status: {response.status_code}")
            print(f"  Count: {response_data['count']}")
            print(f"  Results items: {len(response_data['results'])}")
            return True
            
    except Exception as e:
        print(f"{Colors.FAIL}Error testing endpoint: {str(e)}{Colors.ENDC}")
        return False


def main():
    """Main function to test all endpoints"""
    print(f"{Colors.BOLD}API Response Format Test{Colors.ENDC}")
    print("=" * 50)
    
    # Get authentication token
    token = get_auth_token()
    if not token:
        print(f"{Colors.WARNING}Proceeding without authentication token. Some tests may fail.{Colors.ENDC}")
    
    # Track test results
    results = {
        'passed': 0,
        'failed': 0,
        'total': 0,
        'skipped': 0
    }
    
    # Test all endpoints
    for category, endpoints in ENDPOINTS.items():
        print(f"\n{Colors.BOLD}{category.upper()} ENDPOINTS{Colors.ENDC}")
        print("-" * 50)
        
        for name, url in endpoints.items():
            results['total'] += 1
            
            # Determine method based on endpoint type
            method = 'GET'
            data = None
            
            # Special handling for certain endpoints
            if name == 'logout' or name == 'change_password':
                method = 'POST'
                if name == 'change_password':
                    data = {
                        'old_password': 'oldpassword',  # These won't work but we're just testing format
                        'new_password': 'newpassword'
                    }
            
            # Skip certain endpoints if no token
            if not token and (category != 'auth' or name != 'token'):
                print(f"{Colors.WARNING}Skipping {url} - requires authentication{Colors.ENDC}")
                results['skipped'] += 1
                continue
                
            if test_endpoint(url, token, method=method, data=data):
                results['passed'] += 1
            else:
                results['failed'] += 1
            print("-" * 30)
    
    # Print summary
    print("\n" + "=" * 50)
    print(f"{Colors.BOLD}TEST SUMMARY{Colors.ENDC}")
    print(f"Total tests: {results['total']}")
    print(f"{Colors.OKGREEN}Passed: {results['passed']}{Colors.ENDC}")
    if results['failed'] > 0:
        print(f"{Colors.FAIL}Failed: {results['failed']}{Colors.ENDC}")
    else:
        print(f"Failed: {results['failed']}")
    if results['skipped'] > 0:
        print(f"{Colors.WARNING}Skipped: {results['skipped']}{Colors.ENDC}")
    
    if results['failed'] == 0 and results['skipped'] == 0:
        print(f"\n{Colors.OKGREEN}All endpoints are using the standardized response format!{Colors.ENDC}")
    elif results['failed'] == 0:
        print(f"\n{Colors.WARNING}All tested endpoints are using the standardized response format.{Colors.ENDC}")
        print(f"Some endpoints were skipped due to authentication requirements.")
    else:
        print(f"\n{Colors.WARNING}Some endpoints are not using the standardized response format.{Colors.ENDC}")
        print("Please check the failed tests and update the corresponding views.")
        
    # Return exit code based on results
    return 0 if results['failed'] == 0 else 1


if __name__ == "__main__":
    main()
