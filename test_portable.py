"""Regression tests for the standalone public teaching case."""
from hashlib import sha256
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from app.case_files import ROOT, case_index, read_cache_bytes
from app.cockpit_comparison import build_cockpit_comparison
from app.teacher_case import bootstrap, microcourses, overview


class PortableCaseTests(unittest.TestCase):
    def test_checkout_at_new_path_without_upstream(self):
        with tempfile.TemporaryDirectory() as directory, patch("socket.socket.connect", side_effect=AssertionError("unexpected network call")):
            case = Path(directory) / "独立 案例"
            shutil.copytree(ROOT, case)
            index = case_index(case)
            for relative, meta in index["records"].items():
                data = read_cache_bytes(case, relative)
                self.assertEqual(json.loads(data)["input_hash"], meta["input_hash"])
                self.assertEqual(sha256(data).hexdigest(), meta["public_sha256"])
                self.assertRegex(meta["original_sha256"], r"^[0-9a-f]{64}$")
            output = build_cockpit_comparison(case)
            self.assertEqual(output["display"]["总耗时"]["显示"], "526.8 s")
            self.assertEqual(len(output["display"]["步骤详情"]), 8)
            self.assertEqual(bootstrap(case)["classroom"]["classroom"]["top_three_count"], 23)
            self.assertEqual([p["decision_status"] for p in overview(case)["plans"]], ["待定"] * 3)
            self.assertEqual(len(microcourses(case)["microcourses"]), 3)

    def test_corrupted_cached_evidence_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            case = Path(directory) / "case"
            shutil.copytree(ROOT, case)
            ledger = json.loads((case / "artifacts/evidence/sources.json").read_bytes())
            with (case / ledger[0]["cache_path"]).open("ab") as file:
                file.write(b"\n")
            with self.assertRaisesRegex(ValueError, "哈希"):
                build_cockpit_comparison(case)
