"""
Manual API Response Format Test Script

This script uses Django's test client to verify the response format of key API endpoints.
"""

import os
import sys
import json
import django

# Set up Django environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ASY_CORE.settings')
django.setup()

# Import Django components
from django.test import Client
from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token

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

def test_endpoint(client, url, method='get', data=None, authenticated=False):
    """Test a specific endpoint for standardized response format"""
    print(f"\nTesting endpoint: {url}")
    print("-" * 30)
    
    # Make the request
    if method.lower() == 'get':
        response = client.get(url)
    elif method.lower() == 'post':
        response = client.post(url, data=data, content_type='application/json')
    else:
        print_error(f"Unsupported method: {method}")
        return False
    
    # Check if response is successful
    if response.status_code >= 400:
        print_error(f"Request failed with status code: {response.status_code}")
        print(response.content.decode('utf-8'))
        return False
    
    # Parse response content
    try:
        response_data = json.loads(response.content.decode('utf-8'))
    except json.JSONDecodeError:
        print_error("Response is not valid JSON")
        print(response.content.decode('utf-8'))
        return False
    
    # Check response format
    return check_response_format(response_data)

def main():
    """Main function to test key endpoints"""
    print_header("Manual API Response Format Test")
    
    # Create test client
    client = Client()
    
    # Create or get test user
    User = get_user_model()
    username = 'testuser'
    password = 'testpassword'
    
    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        user = User.objects.create_user(username=username, password=password)
    
    # Authenticate client
    client.login(username=username, password=password)
    
    # Test endpoints
    endpoints = [
        # Documents endpoints
        {'url': '/api/documents/', 'method': 'get'},
        {'url': '/api/documents/stats/', 'method': 'get'},
        
        # Departments endpoints
        {'url': '/api/departments/', 'method': 'get'},
        
        # Users endpoints
        {'url': '/api/users/', 'method': 'get'},
        {'url': '/api/auth/user/', 'method': 'get'},
    ]
    
    results = {'passed': 0, 'failed': 0, 'total': len(endpoints)}
    
    for endpoint in endpoints:
        if test_endpoint(client, **endpoint):
            results['passed'] += 1
        else:
            results['failed'] += 1
    
    # Print summary
    print_header("TEST SUMMARY")
    print(f"Total tests: {results['total']}")
    print(f"Passed: {results['passed']}")
    print(f"Failed: {results['failed']}")
    
    if results['failed'] == 0:
        print_success("\nAll tested endpoints are using the standardized response format!")
    else:
        print_warning("\nSome endpoints are not using the standardized response format.")
        print("Please check the failed tests and update the corresponding views.")

if __name__ == "__main__":
    main()
