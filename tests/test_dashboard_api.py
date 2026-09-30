import sys
import unittest
from pathlib import Path

DASHBOARD_ROOT = Path(__file__).resolve().parents[1] / "src" / "dashboard"
sys.path.insert(0, str(DASHBOARD_ROOT))

from fastapi.testclient import TestClient

from backend.main import app


class TestDashboardApi(unittest.TestCase):
    def test_hello(self):
        client = TestClient(app)
        response = client.get("/api/hello")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("message", body)
        self.assertEqual(body["message"], "Hello from the dashboard API")


if __name__ == "__main__":
    unittest.main()
