import csv
import json
import unittest
from pathlib import Path


class PublicFixtureTests(unittest.TestCase):
    def test_fixture_is_anonymized_minimal_and_referentially_complete(self):
        root = Path(__file__).resolve().parents[1] / "fixtures" / "public"
        preferences = [
            json.loads(line)
            for line in (root / "preferences.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        with (root / "features.csv").open(newline="", encoding="utf-8") as handle:
            features = list(csv.DictReader(handle))
        manifest = json.loads((root / "fixture-manifest.json").read_text(encoding="utf-8"))
        candidates = json.loads(
            (root / "candidate_manifest.json").read_text(encoding="utf-8")
        )["candidates"]

        candidate_ids = {row["candidate_id"] for row in features}
        self.assertEqual(len(preferences), 9)
        self.assertEqual(len(features), 17)
        self.assertEqual(len({row["source_id"] for row in preferences}), 3)
        self.assertFalse(manifest["independent_reviewer_identity_confirmed"])
        self.assertEqual(manifest["repeated_pair_count"], 0)
        self.assertTrue(
            all(
                candidate["artifact_paths"]["output"].endswith(".png")
                and (root.parents[1] / candidate["artifact_paths"]["output"]).is_file()
                for candidate in candidates
            )
        )
        self.assertTrue(
            all(
                row["candidate_a"] in candidate_ids and row["candidate_b"] in candidate_ids
                for row in preferences
            )
        )
        serialized = json.dumps(preferences) + json.dumps(features)
        self.assertNotIn("/Users/", serialized)
        self.assertNotIn("artifact_", serialized)
        self.assertNotIn("timestamp", serialized)
        self.assertNotIn("notes", serialized)


if __name__ == "__main__":
    unittest.main()
