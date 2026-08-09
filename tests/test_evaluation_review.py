import csv
import json
import tempfile
import unittest
from pathlib import Path

from stringartio_preference_lab.evaluation import (
    evaluate_preference_model,
    evaluate_folds,
    grouped_folds,
    human_outcome_summary,
    reviewer_agreement,
)
from stringartio_preference_lab.config import LabConfig
from stringartio_preference_lab.review_app import REVIEW_INTERFACE_ID, ReviewStore
from stringartio_preference_lab.schema import Candidate, Preference


class EvaluationTests(unittest.TestCase):
    def test_end_to_end_report_writes_constraint_and_holdout_sections(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            lab = root / "lab"
            stringartio = root / "stringartio"
            experiments = stringartio / "experiments"
            experiments.mkdir(parents=True)
            paths = {
                "feature": lab / "features.csv",
                "manifest": lab / "candidate_manifest.json",
                "preferences": lab / "preferences.jsonl",
                "output": lab / "evaluation.json",
            }
            paths["feature"].parent.mkdir(parents=True)
            rows = [
                feature_row("a1", "s1", 0.9),
                feature_row("b1", "s1", 0.2),
                feature_row("a2", "s2", 0.8),
                feature_row("b2", "s2", 0.1),
            ]
            with paths["feature"].open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
            manifest_candidates = [
                candidate_dict("a1", "s1", "run-1", 0.9),
                candidate_dict("b1", "s1", "run-1", 0.2),
                candidate_dict("a2", "s2", "run-2", 0.8),
                candidate_dict("b2", "s2", "run-2", 0.1),
            ]
            paths["manifest"].write_text(
                json.dumps({"candidates": manifest_candidates}), encoding="utf-8"
            )
            paths["preferences"].write_text(
                "\n".join(
                    json.dumps(item.to_dict())
                    for item in [
                        preference("p1", "s1", "a1", "b1", "A"),
                        preference("p2", "s2", "a2", "b2", "A"),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            config = LabConfig(
                stringartio_root=str(stringartio),
                experiments_path=str(experiments),
                output_path=str(lab),
                preference_path=str(paths["preferences"]),
                feature_table_path=str(paths["feature"]),
                review_queue_path=str(lab / "queue.jsonl"),
                manifest_path=str(paths["manifest"]),
                model_path=str(lab / "model.json"),
                suggestions_path=str(lab / "suggestions.json"),
            )

            report = evaluate_preference_model(
                config,
                output_path=str(paths["output"]),
                epochs=5,
                min_run_test_pairs=1,
            )

            self.assertTrue(paths["output"].exists())
            self.assertEqual(report["data"]["preference_count"], 2)
            self.assertEqual(report["constraints"]["core_pass_rate"], 1.0)
            self.assertEqual(report["holdout"]["source"]["fold_count"], 2)
            self.assertEqual(report["holdout"]["run"]["fold_count"], 2)
            self.assertFalse(report["evaluation_readiness"]["source_target_met"])
            self.assertFalse(report["evaluation_readiness"]["agreement_estimable"])

    def test_source_holdout_reports_baseline_and_ablations(self):
        rows = {
            "a1": feature_row("a1", "s1", 0.9),
            "b1": feature_row("b1", "s1", 0.2),
            "a2": feature_row("a2", "s2", 0.8),
            "b2": feature_row("b2", "s2", 0.1),
        }
        preferences = [
            preference("p1", "s1", "a1", "b1", "A"),
            preference("p2", "s2", "a2", "b2", "A"),
        ]
        folds = grouped_folds(
            preferences,
            group_value=lambda item: item.source_id,
            train_filter=lambda item, held: item.source_id != held,
            test_filter=lambda item, held: item.source_id == held,
        )

        result = evaluate_folds(folds, rows, 0.05, 20, 0.001)

        self.assertEqual(result["fold_count"], 2)
        self.assertEqual(result["models"]["metric_baseline"]["test_pair_count"], 2)
        self.assertEqual(result["models"]["metric_baseline"]["accuracy"], 1.0)
        self.assertEqual(result["models"]["metric_baseline"]["macro_accuracy"], 1.0)
        self.assertIn("full_reason_flags", result["models"])

        bootstrapped = evaluate_folds(
            folds, rows, 0.05, 20, 0.001, bootstrap_unit="source_id"
        )
        interval = bootstrapped["models"]["metric_baseline"]["source_bootstrap_95_ci"]
        self.assertEqual(interval["source_count"], 2)
        self.assertEqual(interval["accuracy"], {"lower": 1.0, "upper": 1.0})

    def test_human_outcomes_attribute_cross_run_winner(self):
        candidates = {
            "a": candidate("a", "run-old"),
            "b": candidate("b", "run-new"),
        }
        preferences = [
            preference("p1", "source", "a", "b", "B"),
            preference("p2", "source", "a", "b", "both_bad"),
        ]

        result = human_outcome_summary(preferences, candidates)

        matchup = result["cross_run_matchups"][0]
        self.assertEqual(matchup["right_run"], "run-old")
        self.assertEqual(matchup["left_run"], "run-new")
        self.assertEqual(matchup["left_win_rate_decisive"], 1.0)
        self.assertEqual(matchup["both_bad_rate"], 0.5)

    def test_reviewer_agreement_canonicalizes_swapped_candidate_order(self):
        first = preference("p1", "source", "a", "b", "A")
        first.reviewer = "reviewer-1"
        second = preference("p2", "source", "b", "a", "B")
        second.reviewer = "reviewer-2"
        third = preference("p3", "source", "c", "d", "tie")
        third.reviewer = "reviewer-1"
        fourth = preference("p4", "source", "c", "d", "both_bad")
        fourth.reviewer = "reviewer-2"

        result = reviewer_agreement([first, second, third, fourth])

        self.assertEqual(result["overlap_pair_count"], 2)
        self.assertEqual(result["rating_pair_count"], 2)
        self.assertEqual(result["agreement_count"], 1)
        self.assertEqual(result["exact_agreement_rate"], 0.5)
        self.assertIsNotNone(result["chance_corrected_kappa"])


class ReviewStoreTests(unittest.TestCase):
    def test_save_is_append_only_traced_and_duplicate_safe(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            queue_path = root / "queue.jsonl"
            preference_path = root / "preferences.jsonl"
            artifact = root / "candidate.svg"
            artifact.write_text("<svg></svg>", encoding="utf-8")
            queue_path.write_text(
                json.dumps(
                    {
                        "queue_id": "queue-1",
                        "source_id": "source-1",
                        "candidate_a": "candidate-a",
                        "candidate_b": "candidate-b",
                        "blind_artifacts": {"A": str(artifact), "B": str(artifact)},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            store = ReviewStore(queue_path, preference_path, [root], reviewer="reviewer-1")

            status, body = store.save(
                {
                    "queue_id": "queue-1",
                    "winner": "A",
                    "reason_flags": ["cleaner", "unknown"],
                }
            )
            duplicate_status, _ = store.save({"queue_id": "queue-1", "winner": "B"})

            self.assertEqual(status, 200)
            self.assertEqual(duplicate_status, 409)
            self.assertEqual(body["record"]["review_context"]["interface"], REVIEW_INTERFACE_ID)
            self.assertEqual(body["record"]["reason_flags"], ["cleaner"])
            self.assertEqual(store.artifact_path(str(artifact)), artifact.resolve())
            self.assertIsNone(store.artifact_path("/etc/passwd"))
            self.assertEqual(len(preference_path.read_text(encoding="utf-8").splitlines()), 1)
            payload = store.queue_payload()
            self.assertTrue(payload["rows"][0]["saved"])
            self.assertIn("/artifact?path=", payload["rows"][0]["blind_artifact_urls"]["A"])


def feature_row(candidate_id, source_id, score):
    return {
        "candidate_id": candidate_id,
        "source_id": source_id,
        "run_id": "run",
        "score": str(score),
        "metric_visual_quality_score": str(score),
    }


def preference(preference_id, source_id, candidate_a, candidate_b, winner):
    return Preference(
        preference_id=preference_id,
        source_id=source_id,
        candidate_a=candidate_a,
        candidate_b=candidate_b,
        winner=winner,
    )


def candidate(candidate_id, run_id):
    return Candidate(
        run_id=run_id,
        candidate_id=candidate_id,
        source_id="source",
        source_hash=None,
    )


def candidate_dict(candidate_id, source_id, run_id, score):
    return {
        "run_id": run_id,
        "candidate_id": candidate_id,
        "source_id": source_id,
        "source_hash": "hash",
        "config": {
            "qualityModeKey": "clean",
            "lineInk": 0.009,
            "visualOpacityScale": 0.7,
            "visualWidthScale": 0.9,
            "threadCount": 5200,
            "finalLineCap": 5200,
        },
        "metrics": {"visualQualityScore": score, "totalMs": 1000, "finalLineCount": 5200},
        "artifact_paths": {},
        "runtime_ms": 1000,
        "line_count": 5200,
        "app_ready": True,
        "score": score,
    }


if __name__ == "__main__":
    unittest.main()
