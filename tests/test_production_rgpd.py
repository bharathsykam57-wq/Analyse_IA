"""Production RGPD workflow tests.

Validates end-to-end RGPD endpoints in production:
- POST /api/v1/rgpd/consent
- GET /api/v1/rgpd/consent
- GET /api/v1/rgpd/export
- GET /api/v1/rgpd/audit
- DELETE /api/v1/rgpd/erasure

Usage:
    python tests/test_production_rgpd.py --backend-url https://your-backend
"""

import sys
import argparse
import logging
from datetime import datetime
import httpx


logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(asctime)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


class ProductionRGPDTester:
    def __init__(self, backend_url: str, verbose: bool = False):
        self.backend_url = backend_url.rstrip("/")
        self.client = httpx.Client(timeout=20.0, verify=True)
        self.verbose = verbose
        self.email = f"rgpd_{datetime.now().timestamp():.0f}@example.com"
        self.password = "SecureTestPassword123!"
        self.access_token = None
        self.results: list[tuple[str, str]] = []

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
        }

    def _register_and_login(self) -> bool:
        logger.info("[0/5] Register & login...")
        reg = self.client.post(
            f"{self.backend_url}/api/v1/auth/register",
            json={"email": self.email, "password": self.password},
        )
        if reg.status_code not in (200, 201):
            logger.error(f"  ✗ Registration failed: {reg.status_code} {reg.text}")
            self.results.append(("Auth Setup", "FAIL"))
            return False

        login = self.client.post(
            f"{self.backend_url}/api/v1/auth/login",
            json={"email": self.email, "password": self.password},
        )
        if login.status_code != 200:
            logger.error(f"  ✗ Login failed: {login.status_code} {login.text}")
            self.results.append(("Auth Setup", "FAIL"))
            return False

        self.access_token = ((login.json().get("tokens") or {}).get("access_token"))
        if not self.access_token:
            logger.error("  ✗ Access token missing in login response")
            self.results.append(("Auth Setup", "FAIL"))
            return False

        logger.info(f"  ✓ Auth ready for {self.email}")
        self.results.append(("Auth Setup", "PASS"))
        return True

    def test_consent_workflow(self) -> bool:
        logger.info("[1/5] Testing consent create/list...")
        post_resp = self.client.post(
            f"{self.backend_url}/api/v1/rgpd/consent",
            headers=self._headers(),
            json={"purpose": "data_analysis", "granted": True},
        )
        if post_resp.status_code != 201:
            logger.error(f"  ✗ Consent create failed: {post_resp.status_code} {post_resp.text}")
            self.results.append(("Consent Workflow", "FAIL"))
            return False

        list_resp = self.client.get(
            f"{self.backend_url}/api/v1/rgpd/consent",
            headers=self._headers(),
        )
        if list_resp.status_code != 200:
            logger.error(f"  ✗ Consent list failed: {list_resp.status_code} {list_resp.text}")
            self.results.append(("Consent Workflow", "FAIL"))
            return False

        consents = list_resp.json()
        has_data_analysis = any(c.get("purpose") == "data_analysis" for c in consents)
        if not has_data_analysis:
            logger.error("  ✗ data_analysis consent not found in active consents")
            self.results.append(("Consent Workflow", "FAIL"))
            return False

        logger.info("  ✓ Consent workflow passed")
        self.results.append(("Consent Workflow", "PASS"))
        return True

    def test_export_workflow(self) -> bool:
        logger.info("[2/5] Testing data export...")
        resp = self.client.get(
            f"{self.backend_url}/api/v1/rgpd/export",
            headers=self._headers(),
        )
        if resp.status_code != 200:
            logger.error(f"  ✗ Export failed: {resp.status_code} {resp.text}")
            self.results.append(("Data Export", "FAIL"))
            return False

        data = resp.json()
        required_keys = {"user_id", "email", "consents", "audit_logs"}
        if not required_keys.issubset(set(data.keys())):
            logger.error(f"  ✗ Export payload missing keys: expected {required_keys}, got {set(data.keys())}")
            self.results.append(("Data Export", "FAIL"))
            return False

        logger.info("  ✓ Data export payload valid")
        self.results.append(("Data Export", "PASS"))
        return True

    def test_audit_log(self) -> bool:
        logger.info("[3/5] Testing audit retrieval...")
        resp = self.client.get(
            f"{self.backend_url}/api/v1/rgpd/audit",
            headers=self._headers(),
        )
        if resp.status_code != 200:
            logger.error(f"  ✗ Audit retrieval failed: {resp.status_code} {resp.text}")
            self.results.append(("Audit Retrieval", "FAIL"))
            return False

        if not isinstance(resp.json(), list):
            logger.error("  ✗ Audit payload is not a list")
            self.results.append(("Audit Retrieval", "FAIL"))
            return False

        logger.info("  ✓ Audit retrieval passed")
        self.results.append(("Audit Retrieval", "PASS"))
        return True

    def test_erasure(self) -> bool:
        logger.info("[4/5] Testing erasure workflow...")
        resp = self.client.delete(
            f"{self.backend_url}/api/v1/rgpd/erasure",
            headers=self._headers(),
        )
        if resp.status_code != 200:
            logger.error(f"  ✗ Erasure failed: {resp.status_code} {resp.text}")
            self.results.append(("Erasure Workflow", "FAIL"))
            return False

        payload = resp.json()
        if not payload.get("deleted_at"):
            logger.error("  ✗ Erasure response missing deleted_at")
            self.results.append(("Erasure Workflow", "FAIL"))
            return False

        logger.info("  ✓ Erasure workflow passed")
        self.results.append(("Erasure Workflow", "PASS"))
        return True

    def run_all_tests(self) -> bool:
        logger.info("=" * 60)
        logger.info("PRODUCTION RGPD WORKFLOW TESTS")
        logger.info("=" * 60)
        logger.info(f"Backend URL: {self.backend_url}")

        all_pass = True

        if not self._register_and_login():
            all_pass = False
        if not self.test_consent_workflow():
            all_pass = False
        if not self.test_export_workflow():
            all_pass = False
        if not self.test_audit_log():
            all_pass = False
        if not self.test_erasure():
            all_pass = False

        logger.info("\n" + "=" * 60)
        logger.info("TEST SUMMARY")
        logger.info("=" * 60)
        passed = 0
        for name, result in self.results:
            symbol = "✓" if result == "PASS" else "✗"
            logger.info(f"{symbol} {name}: {result}")
            if result == "PASS":
                passed += 1

        logger.info(f"\nResult: {passed}/{len(self.results)} tests passed")
        return all_pass


def main():
    parser = argparse.ArgumentParser(description="Test production RGPD workflow")
    parser.add_argument(
        "--backend-url",
        default="http://localhost:8000",
        help="Backend API URL",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    args = parser.parse_args()

    tester = ProductionRGPDTester(args.backend_url, verbose=args.verbose)
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
