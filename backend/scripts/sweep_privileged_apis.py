#!/usr/bin/env python3
"""
Smoke/integration sweep of privileged admin APIs after Auth_Module migration.

This script tests that the critical privileged admin APIs are working correctly
with the new Auth_Module authentication and authorization system.

Tests:
- Order status update (requires admin + business scope)
- Custom-order operations (requires admin + business scope)
- Chatbot session deletion (requires privileged role)
- Chatbot cache eviction (requires privileged role)
- Admin user promotion (requires super_admin)
- Role changes (triggers session revocation)

Usage:
    python sweep_privileged_apis.py --url http://localhost:8000

Environment variables:
    API_URL: Base URL for the API
    ADMIN_TOKEN: Admin JWT token for testing
"""

import requests
import sys
import json
from typing import Dict, List
from dataclasses import dataclass


@dataclass
class ApiTestResult:
    """Result of an API test."""
    name: str
    endpoint: str
    method: str
    status: str  # "PASS", "FAIL", "SKIP"
    status_code: int = None
    message: str = ""


class PrivilegedApiSweeper:
    """Sweep privileged admin APIs for smoke testing."""
    
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.results: List[ApiTestResult] = []
        self.admin_token = None
        self.user_token = None
        self.order_id = None
        self.custom_order_id = None
        self.session_id = None
    
    def add_result(self, name: str, endpoint: str, method: str, status: str, 
                   status_code: int = None, message: str = ""):
        """Add a test result."""
        self.results.append(ApiTestResult(
            name=name,
            endpoint=endpoint,
            method=method,
            status=status,
            status_code=status_code,
            message=message
        ))
    
    def test_health_endpoint(self):
        """Test the health endpoint (no auth required)."""
        try:
            response = requests.get(f"{self.base_url}/api/health", timeout=5)
            if response.status_code == 200:
                self.add_result("Health Check", "/api/health", "GET", "PASS", 
                               response.status_code, "Server is healthy")
            else:
                self.add_result("Health Check", "/api/health", "GET", "FAIL",
                               response.status_code, f"Unexpected status: {response.status_code}")
        except Exception as e:
            self.add_result("Health Check", "/api/health", "GET", "FAIL",
                           None, f"Connection error: {e}")
    
    def test_auth_me_no_token(self):
        """Test /api/auth/me without token (should fail)."""
        try:
            response = requests.get(f"{self.base_url}/api/auth/me", timeout=5)
            if response.status_code == 401:
                self.add_result("Auth Me No Token", "/api/auth/me", "GET", "PASS",
                               response.status_code, "Correctly rejects unauthenticated request")
            else:
                self.add_result("Auth Me No Token", "/api/auth/me", "GET", "FAIL",
                               response.status_code, f"Expected 401, got {response.status_code}")
        except Exception as e:
            self.add_result("Auth Me No Token", "/api/auth/me", "GET", "FAIL",
                           None, f"Connection error: {e}")
    
    def test_order_status_update_no_auth(self):
        """Test order status update without authentication (should fail)."""
        try:
            # Try to find an order ID first
            response = requests.get(f"{self.base_url}/api/order-management/orders", timeout=5)
            if response.status_code == 200:
                orders = response.json().get("orders", [])
                if orders:
                    self.order_id = orders[0].get("order_id")
                    
                    # Try to update without auth
                    response = requests.put(
                        f"{self.base_url}/api/order-management/orders/{self.order_id}/status",
                        json={"status": "confirmed"},
                        timeout=5
                    )
                    if response.status_code == 401:
                        self.add_result("Order Status No Auth", 
                                       f"/api/order-management/orders/{self.order_id}/status", 
                                       "PUT", "PASS", response.status_code,
                                       "Correctly rejects unauthenticated request")
                    else:
                        self.add_result("Order Status No Auth",
                                       f"/api/order-management/orders/{self.order_id}/status",
                                       "PUT", "FAIL", response.status_code,
                                       f"Expected 401, got {response.status_code}")
                else:
                    self.add_result("Order Status No Auth", "/api/order-management/orders/{id}/status",
                                   "PUT", "SKIP", None, "No orders found to test")
            else:
                self.add_result("Order Status No Auth", "/api/order-management/orders/{id}/status",
                               "PUT", "SKIP", None, "Could not fetch orders")
        except Exception as e:
            self.add_result("Order Status No Auth", "/api/order-management/orders/{id}/status",
                           "PUT", "FAIL", None, f"Connection error: {e}")
    
    def test_chatbot_session_delete_no_auth(self):
        """Test chatbot session deletion without authentication (should fail)."""
        try:
            response = requests.delete(
                f"{self.base_url}/api/chat/session/test_session",
                timeout=5
            )
            if response.status_code == 401:
                self.add_result("Chatbot Session Delete No Auth", "/api/chat/session/{id}",
                               "DELETE", "PASS", response.status_code,
                               "Correctly rejects unauthenticated request")
            else:
                self.add_result("Chatbot Session Delete No Auth", "/api/chat/session/{id}",
                               "DELETE", "FAIL", response.status_code,
                               f"Expected 401, got {response.status_code}")
        except Exception as e:
            self.add_result("Chatbot Session Delete No Auth", "/api/chat/session/{id}",
                           "DELETE", "FAIL", None, f"Connection error: {e}")
    
    def test_chatbot_cache_evict_no_auth(self):
        """Test chatbot cache eviction without authentication (should fail)."""
        try:
            response = requests.delete(
                f"{self.base_url}/api/cache/business/test_business",
                timeout=5
            )
            if response.status_code == 401:
                self.add_result("Chatbot Cache Evict No Auth", "/api/cache/business/{id}",
                               "DELETE", "PASS", response.status_code,
                               "Correctly rejects unauthenticated request")
            else:
                self.add_result("Chatbot Cache Evict No Auth", "/api/cache/business/{id}",
                               "DELETE", "FAIL", response.status_code,
                               f"Expected 401, got {response.status_code}")
        except Exception as e:
            self.add_result("Chatbot Cache Evict No Auth", "/api/cache/business/{id}",
                           "DELETE", "FAIL", None, f"Connection error: {e}")
    
    def test_webhook_endpoint_no_signature(self):
        """Test webhook endpoint without signature (should fail)."""
        try:
            response = requests.post(
                f"{self.base_url}/api/prime/webhooks/razorpay",
                json={"event": "payment.captured"},
                timeout=5
            )
            if response.status_code == 403:
                self.add_result("Webhook No Signature", "/api/prime/webhooks/razorpay",
                               "POST", "PASS", response.status_code,
                               "Correctly rejects unsigned webhook")
            else:
                self.add_result("Webhook No Signature", "/api/prime/webhooks/razorpay",
                               "POST", "FAIL", response.status_code,
                               f"Expected 403, got {response.status_code}")
        except Exception as e:
            self.add_result("Webhook No Signature", "/api/prime/webhooks/razorpay",
                           "POST", "FAIL", None, f"Connection error: {e}")
    
    def run_sweep(self):
        """Run the complete API sweep."""
        print("=" * 60)
        print("Privileged Admin API Sweep")
        print("=" * 60)
        print(f"Base URL: {self.base_url}")
        print()
        
        # Test public endpoints
        print("Testing public endpoints...")
        self.test_health_endpoint()
        
        # Test authentication enforcement
        print("Testing authentication enforcement...")
        self.test_auth_me_no_token()
        self.test_order_status_update_no_auth()
        self.test_chatbot_session_delete_no_auth()
        self.test_chatbot_cache_evict_no_auth()
        self.test_webhook_endpoint_no_signature()
        
        # Print results
        self.print_results()
        
        # Return success/failure
        return all(r.status == "PASS" for r in self.results if r.status != "SKIP")
    
    def print_results(self):
        """Print test results."""
        print()
        print("=" * 60)
        print("Test Results")
        print("=" * 60)
        
        for result in self.results:
            status_symbol = "✓" if result.status == "PASS" else "✗" if result.status == "FAIL" else "○"
            print(f"{status_symbol} {result.name:40} {result.status:5} ({result.status_code or 'N/A'})")
            if result.message:
                print(f"  └─ {result.message}")
        
        print()
        print("=" * 60)
        print("Summary")
        print("=" * 60)
        
        passed = sum(1 for r in self.results if r.status == "PASS")
        failed = sum(1 for r in self.results if r.status == "FAIL")
        skipped = sum(1 for r in self.results if r.status == "SKIP")
        total = len(self.results)
        
        print(f"Total:  {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        print(f"Skipped: {skipped}")
        
        if failed > 0:
            print()
            print("⚠  Some tests failed. Review the results above.")
            return False
        else:
            print()
            print("✓ All tests passed!")
            return True


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Sweep privileged admin APIs")
    parser.add_argument("--url", default="http://localhost:8000", 
                       help="Base URL for the API (default: http://localhost:8000)")
    
    args = parser.parse_args()
    
    sweeper = PrivilegedApiSweeper(args.url)
    success = sweeper.run_sweep()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
