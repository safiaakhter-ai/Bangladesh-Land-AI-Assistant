"""Flask contract smoke tests. Skip only when Flask is not installed locally."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
try:
    import flask  # noqa: F401
    HAS_FLASK = True
except ImportError:
    HAS_FLASK = False


@unittest.skipUnless(HAS_FLASK, "Install requirements.txt to run Flask API tests")
class ApiContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.previous = {key: os.environ.get(key) for key in ("LAND_DATA_DIR", "LAND_CHAT_DB", "KHATIAN_DB_PATH", "ENABLE_SCRAPER", "ADMIN_API_TOKEN")}
        os.environ["LAND_DATA_DIR"] = cls.temp.name
        os.environ["LAND_CHAT_DB"] = str(Path(cls.temp.name) / "chat_history.db")
        os.environ["KHATIAN_DB_PATH"] = str(Path(cls.temp.name) / "nonexistent.db")
        os.environ["ENABLE_SCRAPER"] = "false"
        os.environ.pop("ADMIN_API_TOKEN", None)
        import app
        cls.service = app.app
        cls.service.testing = True

    @classmethod
    def tearDownClass(cls):
        for key, value in cls.previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        cls.temp.cleanup()

    def setUp(self):
        self.client = self.service.test_client()

    def test_health_without_record_database(self):
        res = self.client.get("/api/health")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json["record_database"], "not_configured")

    def test_create_chat_and_retrieve(self):
        created = self.client.post("/api/chats", json={"title": "Test session"})
        self.assertEqual(created.status_code, 201)
        sid = created.json["session_id"]
        messages = self.client.get(f"/api/chats/{sid}")
        self.assertEqual(messages.status_code, 200)
        self.assertEqual(messages.json, [])
        deleted = self.client.delete(f"/api/chats/{sid}")
        self.assertEqual(deleted.status_code, 200)

    def test_reject_unbounded_or_invalid_input(self):
        self.assertEqual(self.client.post("/api/chats/bad-id/message", json={"message": ""}).status_code, 400)
        self.assertEqual(self.client.get("/api/data/not_a_table").status_code, 400)
        self.assertEqual(self.client.post("/api/reverse-geocode-plot", json={"lat": "abc", "lon": 91}).status_code, 400)

    def test_scraper_disabled_by_default(self):
        response = self.client.post("/api/start", json={"task_type": "survey"})
        self.assertEqual(response.status_code, 403)

    def test_no_records_means_zero_results(self):
        res = self.client.get("/api/khatians/search?q=test")
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.json["record_database_available"])
        self.assertEqual(res.json["total"], 0)


if __name__ == "__main__":
    unittest.main()
