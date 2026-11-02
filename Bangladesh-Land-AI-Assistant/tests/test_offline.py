"""Offline tests: no API keys, browser, or government service access required."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.create_demo_db import create_demo_db
from scripts.check_database import validate
from rag_engine import LandRecordRAG


class DemoDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.database = Path(self.temp.name) / "demo.db"
        create_demo_db(self.database)
        self.rag = LandRecordRAG(str(self.database))

    def test_schema(self):
        self.assertEqual(validate(self.database), [])

    def test_sample_records_are_labeled(self):
        records, err = self.rag.search_records({"mouza": "নমুনা মৌজা"}, limit=10)
        self.assertIsNone(err)
        self.assertEqual(len(records), 2)
        self.assertTrue(all(r["details"]["DATA_SOURCE"].startswith("DEMO") for r in records))

    def test_exact_khatian(self):
        records, err = self.rag.search_records({"mouza": "নমুনা মৌজা", "khatian_no": "2"}, limit=10)
        self.assertIsNone(err)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["details"]["KHATIAN_NO"], "2")

    def test_missing_record_does_not_invent_match(self):
        records, err = self.rag.search_records({"mouza": "নমুনা মৌজা", "khatian_no": "9999"}, limit=10)
        self.assertIsNone(err)
        self.assertEqual(records, [])

    def test_no_overwrite(self):
        with self.assertRaises(FileExistsError):
            create_demo_db(self.database)


class OfflineNoDatabaseTests(unittest.TestCase):
    def test_missing_database_is_safe(self):
        rag = LandRecordRAG(str(ROOT / "data" / "unavailable-test.db"))
        records, error = rag.search_records({"khatian_no": "1"})
        self.assertEqual(records, [])
        self.assertIsNotNone(error)


if __name__ == "__main__":
    unittest.main()
