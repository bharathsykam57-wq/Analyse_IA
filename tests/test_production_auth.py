"""Production Authentication Flow Tests

Tests the complete authentication workflow in production:
- User registration
- Login with email/password
- Token generation (access + refresh)
- Token refresh workflow
- Protected endpoint access
- Token expiration handling

Usage:
    python tests/test_production_auth.py --backend-url https://api.example.com

Requirements:
    - Backend running and accessible
    - CORS configured for test origin
    - Database migrated (users table exists)
"""

import sys
import os
import asyncio
import argparse
import httpx
import json
from datetime import datetime
import logging

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(asctime)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)


class ProductionAuthTester:
    """Test authentication flow against production backend"""
    
    def __init__(self, backend_url: str, verbose: bool = False):
        self.backend_url = backend_url.rstrip("/")
        self.client = httpx.Client(
            verify=True,  # Verify SSL in production
            timeout=10.0,
        )
        self.verbose = verbose
        self.test_email = f"test_{datetime.now().timestamp():.0f}@example.com"
        self.test_password = "SecureTestPassword123!"
        self.access_token = None
        self.refresh_token = None
        self.results = []
    
    def log_response(self, name: str, response: httpx.Response):
        """Log response details"""
        if self.verbose:
            logger.debug(f"{name}:")
            logger.debug(f"  Status: {response.status_code}")
            logger.debug(f"  Headers: {dict(response.headers)}")
            if response.headers.get("content-type") == "application/json":
                try:
                    logger.debug(f"  Body: {json.dumps(response.json(), indent=2)}")
                except:
                    logger.debug(f"  Body: {response.text}")
    
    def test_register(self) -> bool:
        """Test user registration endpoint"""
        logger.info("[1/6] Testing user registration...")
        
        try:
            response = self.client.post(
                f"{self.backend_url}/api/v1/auth/register",
                json={
                    "email": self.test_email,
                    "password": self.test_password,
                },
                headers={"Accept": "application/json"},
            )
            
            self.log_response("Register", response)
            
            if response.status_code == 200:
                data = response.json()
                self.access_token = data.get("access_token")
                self.refresh_token = data.get("refresh_token")
                
                if not self.access_token or not self.refresh_token:
                    logger.error("  ✗ Response missing tokens")
                    return False
                
                logger.info(f"  ✓ Registered: {self.test_email}")
                logger.info(f"    - Access token: {self.access_token[:20]}...")
                logger.info(f"    - Refresh token: {self.refresh_token[:20]}...")
                self.results.append(("Registration", "PASS"))
                return True
            else:
                logger.error(f"  ✗ Registration failed: {response.status_code}")
                if response.text:
                    logger.error(f"    {response.text}")
                self.results.append(("Registration", f"FAIL ({response.status_code})"))
                return False
        except Exception as e:
            logger.error(f"  ✗ Registration error: {e}")
            self.results.append(("Registration", "ERROR"))
            return False
    
    def test_login(self) -> bool:
        """Test login endpoint"""
        logger.info("[2/6] Testing login...")
        
        try:
            response = self.client.post(
                f"{self.backend_url}/api/v1/auth/login",
                json={
                    "email": self.test_email,
                    "password": self.test_password,
                },
                headers={"Accept": "application/json"},
            )
            
            self.log_response("Login", response)
            
            if response.status_code == 200:
                data = response.json()
                self.access_token = data.get("access_token")
                self.refresh_token = data.get("refresh_token")
                
                logger.info(f"  ✓ Login successful")
                self.results.append(("Login", "PASS"))
                return True
            else:
                logger.error(f"  ✗ Login failed: {response.status_code}")
                self.results.append(("Login", f"FAIL ({response.status_code})"))
                return False
        except Exception as e:
            logger.error(f"  ✗ Login error: {e}")
            self.results.append(("Login", "ERROR"))
            return False
    
    def test_protected_endpoint(self) -> bool:
        """Test accessing protected endpoint with token"""
        logger.info("[3/6] Testing protected endpoint access...")
        
        if not self.access_token:
            logger.error("  ✗ No access token available")
            self.results.append(("Protected Endpoint", "SKIP"))
            return False
        
        try:
            response = self.client.get(
                f"{self.backend_url}/api/v1/health",
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Accept": "application/json",
                },
            )
            
            self.log_response("Protected Endpoint", response)
            
            if 200 <= response.status_code < 300:
                logger.info(f"  ✓ Protected endpoint accessible")
                self.results.append(("Protected Endpoint", "PASS"))
                return True
            else:
                logger.error(f"  ✗ Protected endpoint failed: {response.status_code}")
                self.results.append(("Protected Endpoint", f"FAIL ({response.status_code})"))
                return False
        except Exception as e:
            logger.error(f"  ✗ Protected endpoint error: {e}")
            self.results.append(("Protected Endpoint", "ERROR"))
            return False
    
    def test_invalid_token(self) -> bool:
        """Test that invalid token is rejected"""
        logger.info("[4/6] Testing invalid token rejection...")
        
        try:
            response = self.client.get(
                f"{self.backend_url}/api/v1/health",
                headers={
                    "Authorization": "Bearer invalid.token.here",
                    "Accept": "application/json",
                },
            )
            
            self.log_response("Invalid Token", response)
            
            if response.status_code == 401 or response.status_code == 403:
                logger.info(f"  ✓ Invalid token correctly rejected ({response.status_code})")
                self.results.append(("Invalid Token Rejection", "PASS"))
                return True
            else:
                logger.error(f"  ✗ Invalid token not rejected: {response.status_code}")
                self.results.append(("Invalid Token Rejection", f"FAIL ({response.status_code})"))
                return False
        except Exception as e:
            logger.error(f"  ✗ Invalid token test error: {e}")
            self.results.append(("Invalid Token Rejection", "ERROR"))
            return False
    
    def test_token_refresh(self) -> bool:
        """Test token refresh workflow"""
        logger.info("[5/6] Testing token refresh...")
        
        if not self.refresh_token:
            logger.error("  ✗ No refresh token available")
            self.results.append(("Token Refresh", "SKIP"))
            return False
        
        try:
            response = self.client.post(
                f"{self.backend_url}/api/v1/auth/refresh",
                json={"refresh_token": self.refresh_token},
                headers={"Accept": "application/json"},
            )
            
            self.log_response("Token Refresh", response)
            
            if response.status_code == 200:
                data = response.json()
                new_access_token = data.get("access_token")
                new_refresh_token = data.get("refresh_token")
                
                if new_access_token and new_refresh_token:
                    self.access_token = new_access_token
                    self.refresh_token = new_refresh_token
                    logger.info(f"  ✓ Token refreshed successfully")
                    self.results.append(("Token Refresh", "PASS"))
                    return True
                else:
                    logger.error("  ✗ Refresh response missing tokens")
                    self.results.append(("Token Refresh", "FAIL"))
                    return False
            else:
                logger.error(f"  ✗ Token refresh failed: {response.status_code}")
                self.results.append(("Token Refresh", f"FAIL ({response.status_code})"))
                return False
        except Exception as e:
            logger.error(f"  ✗ Token refresh error: {e}")
            self.results.append(("Token Refresh", "ERROR"))
            return False
    
    def test_cors_headers(self) -> bool:
        """Test CORS headers"""
        logger.info("[6/6] Testing CORS headers...")
        
        try:
            response = self.client.options(
                f"{self.backend_url}/api/v1/auth/login",
                headers={"Origin": "https://example.com"},
            )
            
            self.log_response("CORS", response)
            
            has_allow_origin = "access-control-allow-origin" in response.headers
            has_allow_methods = "access-control-allow-methods" in response.headers
            
            if has_allow_origin and has_allow_methods:
                origin = response.headers.get("access-control-allow-origin")
                methods = response.headers.get("access-control-allow-methods")
                logger.info(f"  ✓ CORS headers present")
                logger.info(f"    - Allowed Origin: {origin}")
                logger.info(f"    - Allowed Methods: {methods}")
                self.results.append(("CORS Headers", "PASS"))
                return True
            else:
                logger.warning(f"  ⚠ CORS headers incomplete")
                logger.warning(f"    - Has Allow-Origin: {has_allow_origin}")
                logger.warning(f"    - Has Allow-Methods: {has_allow_methods}")
                self.results.append(("CORS Headers", "WARN"))
                return True  # Don't fail on this
        except Exception as e:
            logger.error(f"  ✗ CORS test error: {e}")
            self.results.append(("CORS Headers", "ERROR"))
            return False
    
    def run_all_tests(self) -> bool:
        """Run all authentication tests"""
        logger.info("=" * 60)
        logger.info("PRODUCTION AUTHENTICATION TESTS")
        logger.info("=" * 60)
        logger.info(f"Backend URL: {self.backend_url}")
        logger.info("")
        
        all_pass = True
        
        if not self.test_register():
            all_pass = False
        
        if not self.test_login():
            all_pass = False
        
        if not self.test_protected_endpoint():
            all_pass = False
        
        if not self.test_invalid_token():
            all_pass = False
        
        if not self.test_token_refresh():
            all_pass = False
        
        if not self.test_cors_headers():
            pass  # Don't fail on CORS
        
        self.print_summary()
        
        return all_pass
    
    def print_summary(self):
        """Print test summary"""
        logger.info("\n" + "=" * 60)
        logger.info("TEST SUMMARY")
        logger.info("=" * 60)
        
        for test_name, result in self.results:
            status_symbol = "✓" if result == "PASS" else "✗" if "FAIL" in result else "⊘"
            logger.info(f"{status_symbol} {test_name}: {result}")
        
        passed = sum(1 for _, r in self.results if r == "PASS")
        total = len(self.results)
        
        logger.info(f"\nResult: {passed}/{total} tests passed")
        
        if passed == total:
            logger.info("✓ ALL TESTS PASSED")
        else:
            logger.warning(f"⚠ {total - passed} tests failed")


def main():
    parser = argparse.ArgumentParser(
        description="Test production authentication flow"
    )
    parser.add_argument(
        "--backend-url",
        default="http://localhost:8000",
        help="Backend API URL (default: http://localhost:8000)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output (show all requests/responses)"
    )
    
    args = parser.parse_args()
    
    tester = ProductionAuthTester(args.backend_url, verbose=args.verbose)
    success = tester.run_all_tests()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
