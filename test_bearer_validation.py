#!/usr/bin/env python3
"""
Test script for Bearer token validation in agent_data_push endpoint
"""
import json
import sys
import os

# Add the project to path
sys.path.insert(0, '/home/nfs/hp-g2/dev/python/django/nexhub')

# Set up Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nexhub.settings')

# Import Django
import django
django.setup()

# Import necessary functions
from django.test import RequestFactory
from overwatch.views import agent_data_push
from django.http import JsonResponse

def test_bearer_token_validation():
    """Test Bearer token validation"""
    factory = RequestFactory()
    
    # Test 1: Valid Bearer token
    print("\n[TEST 1] Valid Bearer token...")
    payload = {
        "hostname": "test-server-01",
        "uuid": "550e8400-e29b-41d4-a716-446655440000",
        "ip_address": "192.168.1.10",
        "nic_mac": "00:11:22:33:44:55",
        "os": "Ubuntu",
        "os_version": "22.04",
        "cpu": "Intel(R) Xeon(R) CPU E5-2699 v4 @ 2.20GHz",
        "core_count": 8,
        "sockets": 1,
        "total_mem": 64,
        "disk_count": 2
    }
    
    request = factory.post(
        '/overwatch/api/agent/data/',
        data=json.dumps(payload),
        content_type='application/json',
        HTTP_AUTHORIZATION='Bearer test-shared-key-1765595205'
    )
    response = agent_data_push(request)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.content.decode()}")
    
    if response.status_code == 200:
        print("✓ Valid token accepted")
    else:
        print(f"✗ Unexpected status code: {response.status_code}")
    
    # Test 2: Invalid Bearer token
    print("\n[TEST 2] Invalid Bearer token...")
    request = factory.post(
        '/overwatch/api/agent/data/',
        data=json.dumps(payload),
        content_type='application/json',
        HTTP_AUTHORIZATION='Bearer invalid-key'
    )
    response = agent_data_push(request)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.content.decode()}")
    
    if response.status_code == 401:
        print("✓ Invalid token rejected with 401")
    else:
        print(f"✗ Unexpected status code: {response.status_code}")
    
    # Test 3: Missing Authorization header
    print("\n[TEST 3] Missing Authorization header...")
    request = factory.post(
        '/overwatch/api/agent/data/',
        data=json.dumps(payload),
        content_type='application/json'
    )
    response = agent_data_push(request)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.content.decode()}")
    
    if response.status_code == 401:
        print("✓ Missing header rejected with 401")
    else:
        print(f"✗ Unexpected status code: {response.status_code}")
    
    # Test 4: Malformed Authorization header
    print("\n[TEST 4] Malformed Authorization header (no Bearer prefix)...")
    request = factory.post(
        '/overwatch/api/agent/data/',
        data=json.dumps(payload),
        content_type='application/json',
        HTTP_AUTHORIZATION='test-shared-key-1765595205'
    )
    response = agent_data_push(request)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.content.decode()}")
    
    if response.status_code == 401:
        print("✓ Malformed header rejected with 401")
    else:
        print(f"✗ Unexpected status code: {response.status_code}")
    
    print("\n" + "=" * 80)
    print("Bearer token validation tests complete!")
    print("=" * 80)

if __name__ == '__main__':
    try:
        test_bearer_token_validation()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
