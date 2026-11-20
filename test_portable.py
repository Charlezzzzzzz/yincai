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
from serve import create_app
from test_review import request


class PortableCaseTests(unittest.TestCase):
    def test_roundtable_static_assets_and_private_source(self):
        seats = {"analyst", "expert", "designer", "producer", "checker", "assistant"}
        with tempfile.TemporaryDirectory() as directory:
            app = create_app(Path(directory) / "private.sqlite3")
            status, camera = request(app, "GET", "/roundtable/camera.json")
            self.assertEqual(status, 200)
            self.assertEqual(set(camera["projectedActors"]), seats)
            for target in [*camera["projectedActors"].values(), camera["bookPage"]]:
                self.assertEqual(len(target["bounds"]), 4)
                self.assertGreater(len(target["hitPolygon"]), 3)
            for name in ("assembly.glb", "hero.png", "scene.mjs", "three-viewer.mjs"):
                status, content = request(app, "GET", "/roundtable/" + name)
                self.assertEqual(status, 200, name)
                self.assertTrue(content, name)
            for name in ("source/layout.json", "source/build.py", "../serve.py"):
                self.assertEqual(request(app, "GET", "/roundtable/" + name)[0], 404, name)

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
