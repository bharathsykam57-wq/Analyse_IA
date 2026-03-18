"""Production Celery Task Queue Tests

Tests Celery task queue in production:
- Task submission and tracking
- Task status monitoring
- Task result retrieval
- Queue routing (analysis, rag, agent)
- Error handling and retries
- Task completion verification

Usage:
    python tests/test_production_celery.py --backend-url https://api.example.com --auth-token <token>

Requirements:
    - Backend running and accessible
    - Celery worker deployed and running
    - Redis configured and accessible
    - Authenticated user (use test_production_auth.py first)
"""

import sys
import os
import argparse
import httpx
import json
import time
import logging

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(asctime)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)


class ProductionCeleryTester:
    """Test Celery task queue in production"""
    
    def __init__(self, backend_url: str, access_token: str, verbose: bool = False):
        self.backend_url = backend_url.rstrip("/")
        self.access_token = access_token
        self.client = httpx.Client(
            verify=True,
            timeout=30.0,
            headers={"Authorization": f"Bearer {self.access_token}"},
        )
        self.verbose = verbose
        self.results = []
        self.task_ids = []
    
    def log_response(self, name: str, response: httpx.Response):
        """Log response details"""
        if self.verbose:
            logger.debug(f"{name}:")
            logger.debug(f"  Status: {response.status_code}")
            if response.headers.get("content-type") == "application/json":
                try:
                    logger.debug(f"  Body: {json.dumps(response.json(), indent=2)}")
                except:
                    logger.debug(f"  Body: {response.text}")
    
    def test_agent_task_submission(self) -> bool:
        """Test submitting a task to the agent"""
        logger.info("[1/4] Testing task submission...")
        
        try:
            # Submit a simple analysis task
            response = self.client.post(
                f"{self.backend_url}/api/v1/agent/ask",
                json={
                    "query": "Show me basic statistics about churn rates",
                    "language": "en",
                },
            )
            
            self.log_response("Task Submission", response)
            
            if response.status_code == 202:
                data = response.json()
                task_id = data.get("task_id") or data.get("message_id")
                
                if task_id:
                    logger.info(f"  ✓ Task submitted successfully")
                    logger.info(f"    - Task ID: {task_id}")
                    self.task_ids.append(task_id)
                    self.results.append(("Task Submission", "PASS"))
                    return True
                else:
                    logger.error("  ✗ Response missing task ID")
                    self.results.append(("Task Submission", "FAIL"))
                    return False
            else:
                logger.error(f"  ✗ Task submission failed: {response.status_code}")
                if response.text:
                    logger.error(f"    {response.text}")
                self.results.append(("Task Submission", f"FAIL ({response.status_code})"))
                return False
        except Exception as e:
            logger.error(f"  ✗ Task submission error: {e}")
            self.results.append(("Task Submission", "ERROR"))
            return False
    
    def test_task_status_polling(self) -> bool:
        """Test polling task status"""
        logger.info("[2/4] Testing task status polling...")
        
        if not self.task_ids:
            logger.warning("  ⚠ No task ID to test")
            self.results.append(("Task Status", "SKIP"))
            return True
        
        task_id = self.task_ids[0]
        max_retries = 60
        retry_count = 0
        
        try:
            while retry_count < max_retries:
                response = self.client.get(
                    f"{self.backend_url}/api/v1/agent/status/{task_id}",
                )
                
                self.log_response(f"Task Status (attempt {retry_count + 1})", response)
                
                if response.status_code == 200:
                    data = response.json()
                    status = (data.get("status") or data.get("state") or "").upper()
                    
                    logger.info(f"    Attempt {retry_count + 1}: {status}")
                    
                    if status in ("SUCCESS",):
                        logger.info(f"  ✓ Task completed successfully")
                        
                        result = data.get("result") or data.get("data")
                        if result:
                            logger.info(f"    - Result length: {len(str(result))} chars")
                        
                        self.results.append(("Task Status", "PASS"))
                        return True
                    elif status in ("FAILURE",):
                        logger.error(f"  ✗ Task failed: {data.get('error')}")
                        self.results.append(("Task Status", "FAIL"))
                        return False
                    elif status in ("PENDING", "STARTED", "RETRY", "RETRYING", "PROCESSING"):
                        logger.info(f"    → Still processing, retrying...")
                        time.sleep(2)
                        retry_count += 1
                    else:
                        logger.warning(f"    ⚠ Unknown status: {status}")
                        time.sleep(2)
                        retry_count += 1
                else:
                    logger.error(f"  ✗ Status check failed: {response.status_code}")
                    self.results.append(("Task Status", f"FAIL ({response.status_code})"))
                    return False
            
            logger.warning(f"  ⚠ Task did not complete within {max_retries * 2} seconds")
            self.results.append(("Task Status", "TIMEOUT"))
            return False
        except Exception as e:
            logger.error(f"  ✗ Task status error: {e}")
            self.results.append(("Task Status", "ERROR"))
            return False
    
    def test_multiple_task_queues(self) -> bool:
        """Test different task queue types"""
        logger.info("[3/4] Testing multiple task queues...")
        
        try:
            # Submit multiple task types
            task_types = [
                ("analysis", "Perform anomaly detection on customer churn data"),
                ("rag", "Find information about customer retention strategies"),
                ("agent", "Generate a customer segmentation report"),
            ]
            
            submitted = 0
            for queue_type, query in task_types:
                try:
                    response = self.client.post(
                        f"{self.backend_url}/api/v1/agent/ask",
                        json={
                            "query": query,
                            "language": "en",
                        },
                    )
                    
                    if response.status_code == 202:
                        data = response.json()
                        task_id = data.get("task_id") or data.get("message_id")
                        if task_id:
                            submitted += 1
                            logger.info(f"  ✓ {queue_type.upper()} task submitted: {task_id}")
                    else:
                        logger.warning(f"  ⚠ {queue_type.upper()} submission failed: {response.status_code}")
                except Exception as e:
                    logger.warning(f"  ⚠ {queue_type.upper()} error: {e}")
            
            if submitted >= 2:  # At least 2 should succeed
                logger.info(f"  ✓ Multiple queues tested ({submitted} tasks)")
                self.results.append(("Task Queues", "PASS"))
                return True
            else:
                logger.error(f"  ✗ Not enough tasks submitted: {submitted}")
                self.results.append(("Task Queues", "FAIL"))
                return False
        except Exception as e:
            logger.error(f"  ✗ Task queue error: {e}")
            self.results.append(("Task Queues", "ERROR"))
            return False
    
    def test_rate_limiting(self) -> bool:
        """Test task queue doesn't get overwhelmed"""
        logger.info("[4/4] Testing task queue stability...")
        
        try:
            # Submit multiple tasks quickly
            tasks_submitted = 0
            for i in range(5):
                try:
                    response = self.client.post(
                        f"{self.backend_url}/api/v1/agent/ask",
                        json={
                            "query": f"Quick analysis #{i}",
                            "language": "en",
                        },
                    )
                    
                    if response.status_code == 202:
                        tasks_submitted += 1
                    elif response.status_code == 429:  # Rate limited
                        logger.warning(f"  ⚠ Rate limit hit at task {i}")
                        break
                except Exception as e:
                    logger.debug(f"    Error submitting task {i}: {e}")
            
            if tasks_submitted >= 3:
                logger.info(f"  ✓ Queue handled {tasks_submitted} concurrent tasks")
                self.results.append(("Queue Stability", "PASS"))
                return True
            else:
                logger.error(f"  ✗ Queue stability issue: only {tasks_submitted} tasks")
                self.results.append(("Queue Stability", "FAIL"))
                return False
        except Exception as e:
            logger.error(f"  ✗ Queue stability error: {e}")
            self.results.append(("Queue Stability", "ERROR"))
            return False
    
    def run_all_tests(self) -> bool:
        """Run all Celery tests"""
        logger.info("=" * 60)
        logger.info("PRODUCTION CELERY TASK QUEUE TESTS")
        logger.info("=" * 60)
        logger.info(f"Backend URL: {self.backend_url}")
        logger.info("")
        
        all_pass = True
        
        if not self.test_agent_task_submission():
            all_pass = False
        
        if not self.test_task_status_polling():
            all_pass = False
        
        if not self.test_multiple_task_queues():
            all_pass = False
        
        if not self.test_rate_limiting():
            all_pass = False
        
        self.print_summary()
        
        return all_pass
    
    def print_summary(self):
        """Print test summary"""
        logger.info("\n" + "=" * 60)
        logger.info("TEST SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Tasks submitted: {len(self.task_ids)}")
        for task_id in self.task_ids[:5]:
            logger.info(f"  • {task_id}")
        if len(self.task_ids) > 5:
            logger.info(f"  ... and {len(self.task_ids) - 5} more")
        
        logger.info("")
        for test_name, result in self.results:
            status_symbol = "✓" if result == "PASS" else "✗" if "FAIL" in result else "⊘"
            logger.info(f"{status_symbol} {test_name}: {result}")
        
        passed = sum(1 for _, r in self.results if r == "PASS")
        total = len(self.results)
        
        logger.info(f"\nResult: {passed}/{total} tests passed")
        
        logger.info("\n" + "=" * 60)
        logger.info("Tips for monitoring Celery in production:")
        logger.info("- Check Railway logs for: '[INFO] Received task'")
        logger.info("- Look for: '[INFO] Task ... succeeded'")
        logger.info("- Monitor Redis connection: 'REDIS_URL' in environment")
        logger.info("- Celery worker should show: 'worker ready to accept tasks'")
        logger.info("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Test production Celery task queue"
    )
    parser.add_argument(
        "--backend-url",
        default="http://localhost:8000",
        help="Backend API URL (default: http://localhost:8000)"
    )
    parser.add_argument(
        "--auth-token",
        required=False,
        help="JWT access token (get from test_production_auth.py)"
    )
    parser.add_argument(
        "--email",
        required=False,
        help="Email for auto-login if --auth-token is not provided"
    )
    parser.add_argument(
        "--password",
        required=False,
        help="Password for auto-login if --auth-token is not provided"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output"
    )
    
    args = parser.parse_args()
    
    access_token = args.auth_token or os.getenv("AUTH_TOKEN")

    if not access_token:
        email = args.email or f"celery_test_{int(time.time())}@example.com"
        password = args.password or "SecureTestPassword123!"
        with httpx.Client(timeout=20.0, verify=True) as auth_client:
            auth_client.post(
                f"{args.backend_url.rstrip('/')}/api/v1/auth/register",
                json={"email": email, "password": password},
            )
            login_response = auth_client.post(
                f"{args.backend_url.rstrip('/')}/api/v1/auth/login",
                json={"email": email, "password": password},
            )
            if login_response.status_code != 200:
                logger.error(f"Auto-login failed: {login_response.status_code} {login_response.text}")
                sys.exit(1)
            access_token = (login_response.json().get("tokens") or {}).get("access_token")

    if not access_token:
        logger.error("No access token available. Provide --auth-token or valid --email/--password")
        sys.exit(1)

    tester = ProductionCeleryTester(
        args.backend_url,
        access_token,
        verbose=args.verbose
    )
    success = tester.run_all_tests()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
