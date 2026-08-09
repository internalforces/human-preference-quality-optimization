import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from stringartio_preference_lab.config import LabConfig
from stringartio_preference_lab.features import build_feature_table
from stringartio_preference_lab.ingest import ingest_experiments
from stringartio_preference_lab.model import train_preference_model
from stringartio_preference_lab.review_queue import generate_review_queue


class EmptyDatasetTest(unittest.TestCase):
    def test_empty_experiments_fail_gracefully(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stringartio = root / "stringartio"
            experiments = stringartio / "experiments"
            experiments.mkdir(parents=True)
            lab = root / "lab"
            config = LabConfig(
                stringartio_root=str(stringartio),
                experiments_path=str(experiments),
                output_path=str(lab / "data" / "processed"),
                preference_path=str(lab / "data" / "preferences" / "preferences.jsonl"),
                feature_table_path=str(lab / "data" / "processed" / "features.csv"),
                review_queue_path=str(lab / "data" / "review_queue" / "review_queue.jsonl"),
                manifest_path=str(lab / "data" / "processed" / "candidate_manifest.json"),
                model_path=str(lab / "data" / "processed" / "preference_model.json"),
                suggestions_path=str(lab / "data" / "suggestions" / "suggested-configs.json"),
            )

            manifest = ingest_experiments(config)
            self.assertEqual(manifest["candidate_count"], 0)
            self.assertGreaterEqual(len(manifest["warnings"]), 1)

            features = build_feature_table(config)
            self.assertEqual(features["row_count"], 0)

            queue = generate_review_queue(config)
            self.assertEqual(queue["written_count"], 0)

            model = train_preference_model(config)
            self.assertFalse(model["trained"])
            self.assertEqual(model["method"], "neutral")


if __name__ == "__main__":
    unittest.main()
