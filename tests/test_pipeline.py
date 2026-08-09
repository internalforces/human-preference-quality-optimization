import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from stringartio_preference_lab.config import LabConfig
from stringartio_preference_lab.cli import build_parser
from stringartio_preference_lab.demo import DEMO_FILENAMES, run_public_demo
from stringartio_preference_lab.features import build_feature_table
from stringartio_preference_lab.ingest import ingest_experiments, load_candidate_manifest
from stringartio_preference_lab.model import REASON_FLAG_FEATURE_TARGETS, select_feature_columns, train_preference_model
from stringartio_preference_lab.optimizer import (
    DEFAULT_PREFERRED_LINE_COUNT_MAX,
    DEFAULT_PREFERRED_LINE_COUNT_MIN,
    DEFAULT_MIN_VISIBLE_INK,
    DEFAULT_MIN_VISUAL_OPACITY_SCALE,
    DEFAULT_MIN_VISUAL_WIDTH_SCALE,
    DEFAULT_TARGET_LINE_INK,
    DEFAULT_TARGET_VISIBLE_INK,
    DEFAULT_TARGET_VISUAL_OPACITY_SCALE,
    DEFAULT_TARGET_VISUAL_WIDTH_SCALE,
    suggestion_visual_risk,
    suggest_configurations,
)
from stringartio_preference_lab.preferences import validate_preferences
from stringartio_preference_lab.review_queue import generate_review_queue, select_review_rows, visual_risk
from stringartio_preference_lab.schema import Candidate
from stringartio_preference_lab.source_suite import (
    ROBUSTNESS_SOURCE_SPECS,
    build_source_suite,
    validate_runner_robustness_dataset,
)
from stringartio_preference_lab.svg_diagnostics import rendered_svg_diagnostics
from stringartio_preference_lab.utils import sha256_file


class PipelineTest(unittest.TestCase):
    def test_public_demo_writes_complete_fixture_pipeline(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_public_demo(tmp)

            self.assertEqual(result["scope"], "public_fixture_demo")
            self.assertGreaterEqual(result["candidate_count"], 10)
            self.assertLessEqual(result["candidate_count"], 30)
            self.assertGreater(result["review_queue_count"], 0)
            self.assertTrue(result["model_trained"])
            for filename in DEMO_FILENAMES:
                self.assertTrue((Path(tmp) / filename).is_file())

            suggestions = json.loads(
                (Path(tmp) / "suggested-configs.json").read_text(encoding="utf-8")
            )
            self.assertFalse(suggestions["bayesian_optimization"])
            self.assertEqual(suggestions["method"], "constrained-preference-guided-search")
            self.assertTrue(suggestions["suggestions"])
            self.assertTrue(
                all(item["status"] == "not_executed" for item in suggestions["suggestions"])
            )
            self.assertEqual(
                suggestions["constraints"]["generation_quality_contract"]["source_path"],
                "docs/string-art/generation-quality-contract.json",
            )

    def test_svg_diagnostics_extracts_stroke_stats_and_warnings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            svg_path = root / "strokes.svg"
            svg_path.write_text(
                """
                <svg xmlns="http://www.w3.org/2000/svg">
                  <line stroke="#000" x1="0" y1="0" x2="1" y2="1" />
                  <g opacity="0.5" stroke="#111" stroke-width="2">
                    <line x1="0" y1="1" x2="1" y2="2" />
                    <path d="M 0 0 L 1 1" style="stroke-opacity:40%;stroke-width:4" />
                  </g>
                  <line stroke="none" x1="2" y1="2" x2="3" y2="3" />
                </svg>
                """,
                encoding="utf-8",
            )

            diagnostics = rendered_svg_diagnostics(str(svg_path))

            self.assertTrue(diagnostics["valid"])
            self.assertEqual(diagnostics["line_count"], 3)
            self.assertAlmostEqual(diagnostics["stroke_opacity_min"], 0.2)
            self.assertAlmostEqual(diagnostics["stroke_opacity_mean"], (1.0 + 0.5 + 0.2) / 3)
            self.assertEqual(diagnostics["stroke_width_min"], 1.0)
            self.assertEqual(diagnostics["stroke_width_max"], 4.0)
            self.assertEqual(diagnostics["missing_stroke_opacity_count"], 2)
            self.assertEqual(diagnostics["missing_stroke_width_count"], 1)

            malformed_path = root / "bad.svg"
            malformed_path.write_text("<svg><line", encoding="utf-8")
            malformed = rendered_svg_diagnostics(str(malformed_path))

            self.assertFalse(malformed["valid"])
            self.assertTrue(any("invalid_svg" in warning for warning in malformed["warnings"]))

    def test_end_to_end_small_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = make_fixture(Path(tmp))

            manifest = ingest_experiments(config)
            self.assertEqual(manifest["candidate_count"], 2)
            self.assertTrue(Path(config.manifest_path).exists())

            candidates = load_candidate_manifest(config.manifest_path)
            self.assertEqual({candidate.source_id for candidate in candidates}, {"pair-1"})
            self.assertTrue(all(candidate.app_ready for candidate in candidates))

            features = build_feature_table(config)
            self.assertEqual(features["row_count"], 2)
            self.assertIn("rendered_svg_stroke_opacity_mean", features["columns"])
            self.assertIn("rendered_svg_stroke_width_mean", features["columns"])
            self.assertTrue(Path(config.feature_table_path).exists())

            queue = generate_review_queue(config, limit=10)
            self.assertEqual(queue["written_count"], 1)
            self.assertTrue(Path(config.review_queue_path).exists())

            write_jsonl(
                Path(config.preference_path),
                [
                    {
                        "preference_id": "pref-001",
                        "source_id": "pair-1",
                        "candidate_a": candidates[0].candidate_id,
                        "candidate_b": candidates[1].candidate_id,
                        "winner": "A",
                        "reason_flags": ["cleaner"],
                    }
                ],
            )
            preference_report = validate_preferences(config)
            self.assertEqual(preference_report["warning_count"], 0)

            model = train_preference_model(config, epochs=20)
            self.assertTrue(model["trained"])
            self.assertEqual(model["training_examples"], 2)
            self.assertEqual(model["pairwise_training_examples"], 1)
            self.assertEqual(model["reason_flag_training_examples"], 1)
            self.assertEqual(model["reason_flag_signal"]["used_flags"], {"cleaner": 1})
            self.assertIn(
                "metric_line_clump_penalty",
                model["reason_flag_signal"]["used_features"]["cleaner"],
            )

            suggestions = suggest_configurations(config, limit=3, runtime_limit_ms=30000)
            self.assertGreaterEqual(len(suggestions["suggestions"]), 1)
            self.assertTrue(Path(config.suggestions_path).exists())

    def test_ingest_cli_accepts_run_id_option(self):
        args = build_parser().parse_args(["ingest", "--run-id=run-a", "--dry-run"])

        self.assertEqual(args.command, "ingest")
        self.assertEqual(args.run_id, "run-a")
        self.assertTrue(args.dry_run)

    def test_ingest_run_id_filters_to_requested_local_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = make_fixture(Path(tmp))
            add_fixture_artwork_run(config, "run-b", "c", 0.68, 0.61)

            default_manifest = ingest_experiments(config, dry_run=True)
            filtered_manifest = ingest_experiments(config, dry_run=True, run_id="run-b")

            self.assertEqual(default_manifest["candidate_count"], 3)
            self.assertEqual(default_manifest["source"]["run_dir_count"], 2)
            self.assertEqual(filtered_manifest["candidate_count"], 1)
            self.assertEqual(filtered_manifest["source"]["run_dir_count"], 1)
            self.assertEqual(filtered_manifest["source"]["requested_run_id"], "run-b")
            self.assertEqual(
                {candidate["run_id"] for candidate in filtered_manifest["candidates"]},
                {"run-b"},
            )

    def test_ingest_run_id_missing_returns_warning_and_empty_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = make_fixture(Path(tmp))

            manifest = ingest_experiments(config, dry_run=True, run_id="missing-run")

            self.assertEqual(manifest["candidate_count"], 0)
            self.assertEqual(manifest["source"]["run_dir_count"], 0)
            self.assertTrue(
                any(
                    warning["message"] == "Requested runId not found"
                    for warning in manifest["warnings"]
                )
            )

    def test_ingest_run_id_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = make_fixture(Path(tmp))

            manifest = ingest_experiments(config, dry_run=True, run_id="../run-a")

            self.assertEqual(manifest["candidate_count"], 0)
            self.assertEqual(manifest["source"]["run_dir_count"], 0)
            self.assertTrue(
                any(
                    warning["message"] == "Requested runId must be a single path segment"
                    for warning in manifest["warnings"]
                )
            )

    def test_ingest_run_id_accepts_configured_run_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = make_fixture(Path(tmp))
            config.experiments_path = str(Path(config.experiments_path) / "local-runs" / "run-a")

            manifest = ingest_experiments(config, dry_run=True, run_id="run-a")

            self.assertEqual(manifest["candidate_count"], 2)
            self.assertEqual(manifest["source"]["run_dir_count"], 1)
            self.assertEqual(
                {candidate["run_id"] for candidate in manifest["candidates"]},
                {"run-a"},
            )

    def test_both_bad_preferences_create_failure_signal(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = make_fixture(Path(tmp))

            ingest_experiments(config)
            candidates = load_candidate_manifest(config.manifest_path)
            build_feature_table(config)

            write_jsonl(
                Path(config.preference_path),
                [
                    {
                        "preference_id": "pref-both-bad-001",
                        "source_id": "pair-1",
                        "candidate_a": candidates[0].candidate_id,
                        "candidate_b": candidates[1].candidate_id,
                        "winner": "both_bad",
                    }
                ],
            )

            model = train_preference_model(config, epochs=20)
            self.assertTrue(model["trained"])
            self.assertEqual(model["pairwise_training_examples"], 0)
            self.assertEqual(model["tie_training_examples"], 0)
            self.assertEqual(model["failure_training_examples"], 2)
            self.assertEqual(model["training_examples"], 2)

            for candidate in candidates:
                score = model["candidate_scores"][candidate.candidate_id]
                self.assertEqual(score["both_bad_count"], 1.0)
                self.assertGreater(score["failure_penalty"], 0.0)
                self.assertIn("raw_preference_score", score)

    def test_tie_preferences_create_weak_equal_preference_signal(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = make_fixture(Path(tmp))

            ingest_experiments(config)
            candidates = load_candidate_manifest(config.manifest_path)
            build_feature_table(config)

            write_jsonl(
                Path(config.preference_path),
                [
                    {
                        "preference_id": "pref-tie-001",
                        "source_id": "pair-1",
                        "candidate_a": candidates[0].candidate_id,
                        "candidate_b": candidates[1].candidate_id,
                        "winner": "tie",
                    }
                ],
            )

            model = train_preference_model(config, epochs=20)
            self.assertTrue(model["trained"])
            self.assertEqual(model["pairwise_training_examples"], 0)
            self.assertEqual(model["tie_training_examples"], 1)
            self.assertEqual(model["failure_training_examples"], 0)
            self.assertEqual(model["training_examples"], 1)
            self.assertEqual(model["tie_signal"]["training_weight"], 0.25)

            for candidate in candidates:
                score = model["candidate_scores"][candidate.candidate_id]
                self.assertEqual(score["both_bad_count"], 0.0)
                self.assertEqual(score["failure_penalty"], 0.0)

    def test_ingest_attaches_rendered_svg_diagnostics_to_candidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = make_fixture(Path(tmp))

            ingest_experiments(config)
            candidates = load_candidate_manifest(config.manifest_path)

            self.assertTrue(candidates)
            for candidate in candidates:
                rendered_svg = candidate.metadata.get("rendered_svg") or {}
                self.assertTrue(rendered_svg["valid"])
                self.assertGreater(rendered_svg["line_count"], 0)
                self.assertIn("stroke_opacity_mean", rendered_svg)
                self.assertIn("stroke_width_mean", rendered_svg)

    def test_queue_prioritizes_anchor_mixed_pairs_after_failure_signal(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = make_fixture(Path(tmp))
            write_json(
                Path(config.manifest_path),
                {
                    "schema_version": 1,
                    "candidate_count": 4,
                    "candidates": [
                        make_queue_candidate("anchor-a", score=0.86, clump=0.02, overdraw=0.08, line_count=4800),
                        make_queue_candidate("anchor-b", score=0.82, clump=0.03, overdraw=0.1, line_count=4800),
                        make_queue_candidate("risky-a", score=0.32, clump=0.9, overdraw=0.8, line_count=6000),
                        make_queue_candidate("risky-b", score=0.3, clump=0.92, overdraw=0.85, line_count=6000),
                    ],
                },
            )
            write_json(
                Path(config.model_path),
                {
                    "schema_version": 1,
                    "method": "test-model",
                    "candidate_scores": {
                        "anchor-a": {"win_probability": 0.92, "uncertainty": 0.5, "both_bad_count": 0.0},
                        "anchor-b": {"win_probability": 0.88, "uncertainty": 0.5, "both_bad_count": 0.0},
                        "risky-a": {"win_probability": 0.12, "uncertainty": 0.5, "both_bad_count": 1.0},
                        "risky-b": {"win_probability": 0.1, "uncertainty": 0.5, "both_bad_count": 1.0},
                    },
                },
            )
            write_jsonl(Path(config.preference_path), [])

            queue = generate_review_queue(config, limit=3)
            rows = [
                json.loads(line)
                for line in Path(config.review_queue_path).read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]

            self.assertEqual(queue["written_count"], 3)
            self.assertGreaterEqual(queue["selection_strategy"]["selected_anchor_pair_count"], 2)
            self.assertEqual(queue["selection_strategy"]["selected_double_failure_risk_pair_count"], 0)
            self.assertTrue(any(row["selection_reasons"]["anchor_pair"] > 0 for row in rows))

    def test_rendered_svg_visibility_increases_queue_and_suggestion_risk(self):
        faint = Candidate.from_dict(
            make_queue_candidate(
                "faint-rendered",
                score=0.7,
                clump=0.02,
                overdraw=0.08,
                line_count=4800,
                metadata={
                    "rendered_svg": {
                        "path_present": True,
                        "path_exists": True,
                        "valid": True,
                        "line_count": 100,
                        "stroke_opacity_mean": 0.001,
                        "stroke_width_mean": 0.3,
                        "warning_count": 0,
                    }
                },
            )
        )
        visible = Candidate.from_dict(
            make_queue_candidate(
                "visible-rendered",
                score=0.7,
                clump=0.02,
                overdraw=0.08,
                line_count=4800,
                metadata={
                    "rendered_svg": {
                        "path_present": True,
                        "path_exists": True,
                        "valid": True,
                        "line_count": 100,
                        "stroke_opacity_mean": 0.02,
                        "stroke_width_mean": 1.2,
                        "warning_count": 0,
                    }
                },
            )
        )

        self.assertGreater(visual_risk(faint), visual_risk(visible))
        self.assertGreater(suggestion_visual_risk(faint), suggestion_visual_risk(visible))

    def test_ingest_links_preference_lab_handoff_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = make_fixture(Path(tmp))
            run_dir = Path(config.experiments_path) / "local-runs" / "run-a"
            output_dir = run_dir / "outputs" / "gen-a" / "clean"
            (output_dir / "c.svg").write_text("<svg></svg>", encoding="utf-8")
            (output_dir / "c-comparison.png").write_bytes(b"c")
            write_json(
                run_dir / "results.json",
                {
                    "episodes": [
                        {
                            "runId": "generated-run",
                            "episode": 1,
                            "profileKey": "clean",
                            "score": 0.66,
                            "config": {
                                "qualityModeKey": "clean",
                                "pinCount": 600,
                                "threadCount": 4800,
                                "targetAwareLineReweighting": False,
                                "targetGuidanceStrength": 0,
                            },
                            "metrics": {
                                "inputMinScore": 0.64,
                                "finalLineCount": 4800,
                                "totalMs": 24000,
                            },
                            "artifacts": [
                                {
                                    "inputId": "pair-1",
                                    "sourcePath": "experiments/rl-training/originals/source-1.png",
                                    "targetPath": "experiments/rl-training/targets/target-1.png",
                                    "outputPath": "experiments/local-runs/run-a/outputs/gen-a/clean/c.svg",
                                    "comparisonPath": "experiments/local-runs/run-a/outputs/gen-a/clean/c-comparison.png",
                                    "score": 0.66,
                                }
                            ],
                        }
                    ]
                },
            )
            write_json(
                run_dir / "preference-lab-handoff.json",
                {
                    "runId": "run-a",
                    "suggestions": [
                        {
                            "suggestionId": "suggestion-fixture",
                            "expectedPreferenceScore": 5.5,
                            "phaseId": "suggestion-fixture",
                            "sourceRunId": "experiments",
                            "regenerated": [
                                {
                                    "runId": "generated-run",
                                    "episode": 1,
                                }
                            ],
                        }
                    ],
                },
            )

            ingest_experiments(config)
            candidates = load_candidate_manifest(config.manifest_path)
            linked = [
                candidate
                for candidate in candidates
                if candidate.metadata.get("preference_lab", {}).get("suggestion_id")
                == "suggestion-fixture"
            ]

            self.assertEqual(len(linked), 1)
            self.assertEqual(linked[0].metadata["preference_lab"]["phase_id"], "suggestion-fixture")

            features = build_feature_table(config)
            feature_text = Path(config.feature_table_path).read_text(encoding="utf-8")
            self.assertIn("preference_lab_suggestion_id", features["columns"])
            self.assertIn("suggestion-fixture", feature_text)

    def test_ingest_normalizes_batch_runtime_per_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = make_fixture(Path(tmp))
            run_dir = Path(config.experiments_path) / "local-runs" / "run-a"
            output_dir = run_dir / "outputs" / "batch" / "clean"
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "batch-r1.svg").write_text("<svg></svg>", encoding="utf-8")
            (output_dir / "batch-r2.svg").write_text("<svg></svg>", encoding="utf-8")
            write_json(
                run_dir / "results.json",
                {
                    "episodes": [
                        {
                            "runId": "batch-run",
                            "episode": 1,
                            "profileKey": "clean",
                            "score": 0.62,
                            "repeatCount": 2,
                            "config": {
                                "qualityModeKey": "clean",
                                "pinCount": 600,
                                "threadCount": 4800,
                                "targetAwareLineReweighting": False,
                                "targetGuidanceStrength": 0,
                            },
                            "metrics": {
                                "finalLineCount": 4800,
                                "totalMs": 60000,
                            },
                            "artifacts": [
                                {
                                    "inputId": "pair-1",
                                    "repeat": 1,
                                    "outputPath": "experiments/local-runs/run-a/outputs/batch/clean/batch-r1.svg",
                                    "score": 0.61,
                                },
                                {
                                    "inputId": "pair-1",
                                    "repeat": 2,
                                    "outputPath": "experiments/local-runs/run-a/outputs/batch/clean/batch-r2.svg",
                                    "score": 0.63,
                                },
                            ],
                        }
                    ]
                },
            )

            ingest_experiments(config)
            candidates = load_candidate_manifest(config.manifest_path)
            result_candidates = [
                candidate
                for candidate in candidates
                if candidate.metadata.get("source_kind") == "results-episode"
            ]

            self.assertEqual(len(result_candidates), 2)
            self.assertTrue(all(candidate.runtime_ms == 30000 for candidate in result_candidates))

    def test_ingest_app_ready_heuristic_uses_generation_quality_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = make_fixture(Path(tmp))
            write_json(
                generation_quality_contract_path(config),
                make_generation_quality_contract(runtime_target_ms=21000),
            )
            run_dir = Path(config.experiments_path) / "local-runs" / "run-a"
            output_dir = run_dir / "outputs" / "contract" / "clean"
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "slow.svg").write_text("<svg></svg>", encoding="utf-8")
            (output_dir / "target-aware.svg").write_text("<svg></svg>", encoding="utf-8")
            write_json(
                run_dir / "results.json",
                {
                    "episodes": [
                        {
                            "runId": "contract-run",
                            "episode": 1,
                            "profileKey": "clean",
                            "score": 0.62,
                            "config": {
                                "qualityModeKey": "clean",
                                "pinCount": 600,
                                "threadCount": 5400,
                                "targetAwareLineReweighting": False,
                                "targetGuidanceStrength": 0,
                            },
                            "metrics": {
                                "finalLineCount": 5400,
                                "totalMs": 22000,
                            },
                            "artifacts": [
                                {
                                    "inputId": "pair-1",
                                    "outputPath": "experiments/local-runs/run-a/outputs/contract/clean/slow.svg",
                                    "score": 0.62,
                                }
                            ],
                        },
                        {
                            "runId": "contract-run",
                            "episode": 2,
                            "profileKey": "clean",
                            "score": 0.64,
                            "config": {
                                "qualityModeKey": "clean",
                                "pinCount": 600,
                                "threadCount": 5400,
                                "targetAwareLineReweighting": False,
                                "targetGuidanceStrength": 0.1,
                            },
                            "metrics": {
                                "finalLineCount": 5400,
                                "totalMs": 20000,
                            },
                            "artifacts": [
                                {
                                    "inputId": "pair-1",
                                    "outputPath": "experiments/local-runs/run-a/outputs/contract/clean/target-aware.svg",
                                    "score": 0.64,
                                }
                            ],
                        },
                    ]
                },
            )

            ingest_experiments(config)
            candidates = load_candidate_manifest(config.manifest_path)
            result_candidates = [
                candidate
                for candidate in candidates
                if candidate.metadata.get("source_kind") == "results-episode"
            ]

            self.assertEqual(len(result_candidates), 2)
            self.assertTrue(all(not candidate.app_ready for candidate in result_candidates))
            self.assertEqual(
                {candidate.app_ready_reason for candidate in result_candidates},
                {"not-marked-app-ready"},
            )

    def test_suggest_excludes_low_visibility_anchors(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = make_fixture(Path(tmp))
            write_json(
                Path(config.manifest_path),
                {
                    "schema_version": 1,
                    "candidate_count": 3,
                    "candidates": [
                        make_optimizer_candidate(
                            "too-faint",
                            score=0.99,
                            visual_opacity_scale=0.32,
                            visual_width_scale=0.6,
                            line_ink=0.0083,
                        ),
                        make_optimizer_candidate(
                            "old-floor-metric-best",
                            score=0.98,
                            visual_opacity_scale=0.45,
                            visual_width_scale=0.7,
                            line_ink=0.0083,
                        ),
                        make_optimizer_candidate(
                            "visible",
                            score=0.4,
                            visual_opacity_scale=0.65,
                            visual_width_scale=0.85,
                            line_ink=0.0088,
                        ),
                    ],
                },
            )
            write_json(
                Path(config.model_path),
                {
                    "schema_version": 1,
                    "method": "test-model",
                    "candidate_scores": {
                        "too-faint": {"preference_score": 10.0, "uncertainty": 0.1},
                        "old-floor-metric-best": {"preference_score": 9.0, "uncertainty": 0.1},
                        "visible": {"preference_score": 1.0, "uncertainty": 0.1},
                    },
                },
            )

            suggestions = suggest_configurations(config, limit=3)

            self.assertEqual(suggestions["input"]["eligible_candidate_count"], 1)
            self.assertEqual(
                suggestions["input"]["constraint_rejection_counts"]["visual_opacity_scale_floor"],
                2,
            )
            self.assertEqual(
                suggestions["input"]["constraint_rejection_counts"]["visual_width_scale_floor"],
                2,
            )
            self.assertEqual(
                suggestions["input"]["constraint_rejection_counts"]["line_ink_floor"],
                2,
            )
            self.assertEqual(
                suggestions["input"]["constraint_rejection_counts"]["visible_ink_floor"],
                2,
            )
            self.assertTrue(suggestions["suggestions"])
            self.assertEqual(
                suggestions["suggestions"][0]["provenance"]["optimizer"],
                "constrained-preference-guided-search-v1",
            )
            self.assertFalse(
                suggestions["suggestions"][0]["provenance"]["bayesian_optimization"]
            )
            self.assertTrue(
                all(
                    suggestion["nearest_observed_candidate"] == "visible"
                    for suggestion in suggestions["suggestions"]
                )
            )
            for suggestion in suggestions["suggestions"]:
                proposed = suggestion["config"]
                self.assertGreaterEqual(
                    proposed["visualOpacityScale"],
                    DEFAULT_TARGET_VISUAL_OPACITY_SCALE,
                )
                self.assertGreaterEqual(
                    proposed["visualWidthScale"],
                    DEFAULT_TARGET_VISUAL_WIDTH_SCALE,
                )
                self.assertGreaterEqual(
                    proposed["lineInk"],
                    DEFAULT_TARGET_LINE_INK,
                )
                self.assertGreaterEqual(
                    proposed["finalLineCap"],
                    DEFAULT_PREFERRED_LINE_COUNT_MIN,
                )
                self.assertLessEqual(
                    proposed["finalLineCap"],
                    DEFAULT_PREFERRED_LINE_COUNT_MAX,
                )
                visible_ink = (
                    proposed["lineInk"]
                    * proposed["visualOpacityScale"]
                    * proposed["visualWidthScale"]
                )
                self.assertGreaterEqual(visible_ink, DEFAULT_TARGET_VISIBLE_INK)
                self.assertGreaterEqual(visible_ink, DEFAULT_MIN_VISIBLE_INK)

    def test_suggest_uses_stringartio_generation_quality_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = make_fixture(Path(tmp))
            write_json(
                generation_quality_contract_path(config),
                make_generation_quality_contract(
                    runtime_target_ms=21000,
                    line_count_limit=5500,
                    preferred_line_min=5300,
                    preferred_line_max=5400,
                    min_line_ink=0.0105,
                    target_line_ink=0.011,
                    target_visible_ink=0.007,
                ),
            )
            write_json(
                Path(config.manifest_path),
                {
                    "schema_version": 1,
                    "candidate_count": 1,
                    "candidates": [
                        make_optimizer_candidate(
                            "contract-visible-anchor",
                            score=0.9,
                            visual_opacity_scale=0.8,
                            visual_width_scale=0.9,
                            line_ink=0.011,
                            runtime_ms=19000,
                            line_count=5400,
                        ),
                    ],
                },
            )
            write_json(
                Path(config.model_path),
                {
                    "schema_version": 1,
                    "method": "test-model",
                    "candidate_scores": {
                        "contract-visible-anchor": {"preference_score": 4.0, "uncertainty": 0.1},
                    },
                },
            )

            suggestions = suggest_configurations(config, limit=1)

            constraints = suggestions["constraints"]
            self.assertEqual(constraints["runtime_limit_ms"], 21000)
            self.assertEqual(constraints["line_count_limit"], 5500)
            self.assertEqual(
                constraints["preferred_line_count_range"],
                {"preferred_min": 5300, "preferred_max": 5400},
            )
            self.assertEqual(constraints["visibility"]["target_line_ink"], 0.011)
            self.assertEqual(constraints["visibility"]["target_visible_ink"], 0.007)
            self.assertEqual(
                constraints["generation_quality_contract"]["contract_id"],
                "stringartio-generation-quality-contract",
            )
            self.assertFalse(constraints["generation_quality_contract"]["fallback"])
            self.assertRegex(constraints["generation_quality_contract"]["hash"], r"^[0-9a-f]{64}$")
            self.assertEqual(suggestions["suggestions"][0]["config"]["finalLineCap"], 5400)

    def test_suggest_missing_contract_warns_and_uses_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = make_fixture(Path(tmp))
            generation_quality_contract_path(config).unlink()
            write_json(
                Path(config.manifest_path),
                {
                    "schema_version": 1,
                    "candidate_count": 1,
                    "candidates": [
                        make_optimizer_candidate(
                            "fallback-anchor",
                            score=0.9,
                            visual_opacity_scale=0.8,
                            visual_width_scale=0.9,
                            line_ink=0.009,
                            runtime_ms=22000,
                            line_count=5600,
                        ),
                    ],
                },
            )

            suggestions = suggest_configurations(config, limit=1, dry_run=True)

            contract = suggestions["constraints"]["generation_quality_contract"]
            self.assertTrue(contract["fallback"])
            self.assertIsNone(contract["hash"])
            self.assertEqual(suggestions["constraints"]["runtime_limit_ms"], 30000)
            self.assertTrue(
                any("Generation quality contract missing" in warning["message"] for warning in suggestions["warnings"])
            )

    def test_suggest_reports_rendered_svg_diagnostics_and_penalizes_faint_bases(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = make_fixture(Path(tmp))
            faint_metadata = {
                "rendered_svg": {
                    "path_present": True,
                    "path_exists": True,
                    "valid": True,
                    "line_count": 100,
                    "stroke_opacity_mean": 0.001,
                    "stroke_width_mean": 0.3,
                    "warning_count": 1,
                }
            }
            visible_metadata = {
                "rendered_svg": {
                    "path_present": True,
                    "path_exists": True,
                    "valid": True,
                    "line_count": 100,
                    "stroke_opacity_mean": 0.02,
                    "stroke_width_mean": 1.2,
                    "warning_count": 0,
                }
            }
            write_json(
                Path(config.manifest_path),
                {
                    "schema_version": 1,
                    "candidate_count": 2,
                    "candidates": [
                        make_optimizer_candidate(
                            "faint-rendered-base",
                            score=0.78,
                            visual_opacity_scale=0.7,
                            visual_width_scale=0.9,
                            line_ink=0.009,
                            metadata=faint_metadata,
                        ),
                        make_optimizer_candidate(
                            "visible-rendered-base",
                            score=0.76,
                            visual_opacity_scale=0.7,
                            visual_width_scale=0.9,
                            line_ink=0.009,
                            metadata=visible_metadata,
                        ),
                    ],
                },
            )
            write_json(
                Path(config.model_path),
                {
                    "schema_version": 1,
                    "method": "test-model",
                    "candidate_scores": {
                        "faint-rendered-base": {"preference_score": 0.78, "uncertainty": 0.1},
                        "visible-rendered-base": {"preference_score": 0.76, "uncertainty": 0.1},
                    },
                },
            )

            suggestions = suggest_configurations(config, limit=1)

            self.assertEqual(suggestions["suggestions"][0]["nearest_observed_candidate"], "visible-rendered-base")
            rendered_summary = suggestions["input"]["rendered_svg_diagnostics"]["all_candidates"]
            self.assertEqual(rendered_summary["candidate_count"], 2)
            self.assertEqual(rendered_summary["warning_candidate_count"], 1)
            self.assertEqual(rendered_summary["low_opacity_candidate_count"], 1)
            self.assertEqual(rendered_summary["low_width_candidate_count"], 1)
            self.assertEqual(
                suggestions["suggestions"][0]["provenance"]["base_candidate_diagnostics"][
                    "rendered_svg"
                ]["stroke_width_mean"],
                1.2,
            )

    def test_suggest_steers_high_density_anchor_to_moderate_line_band(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = make_fixture(Path(tmp))
            write_json(
                Path(config.manifest_path),
                {
                    "schema_version": 1,
                    "candidate_count": 1,
                    "candidates": [
                        make_optimizer_candidate(
                            "dense-visible-anchor",
                            score=0.95,
                            visual_opacity_scale=1.0,
                            visual_width_scale=1.0,
                            line_ink=0.009,
                            line_count=6000,
                        ),
                    ],
                },
            )
            write_json(
                Path(config.model_path),
                {
                    "schema_version": 1,
                    "method": "test-model",
                    "candidate_scores": {
                        "dense-visible-anchor": {"preference_score": 5.0, "uncertainty": 0.1},
                    },
                },
            )

            suggestions = suggest_configurations(config, limit=1)

            self.assertEqual(suggestions["input"]["eligible_candidate_count"], 1)
            proposed = suggestions["suggestions"][0]["config"]
            self.assertEqual(proposed["finalLineCap"], DEFAULT_PREFERRED_LINE_COUNT_MAX)
            self.assertEqual(proposed["threadCount"], DEFAULT_PREFERRED_LINE_COUNT_MAX)
            self.assertEqual(
                suggestions["suggestions"][0]["constraints"]["preferred_line_count_range"],
                {
                    "preferred_min": DEFAULT_PREFERRED_LINE_COUNT_MIN,
                    "preferred_max": DEFAULT_PREFERRED_LINE_COUNT_MAX,
                },
            )

    def test_suggest_prefers_stable_base_over_both_bad_observed_base(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = make_fixture(Path(tmp))
            write_json(
                Path(config.manifest_path),
                {
                    "schema_version": 1,
                    "candidate_count": 2,
                    "candidates": [
                        make_optimizer_candidate(
                            "failure-observed",
                            score=0.95,
                            visual_opacity_scale=0.7,
                            visual_width_scale=0.9,
                            line_ink=0.009,
                        ),
                        make_optimizer_candidate(
                            "stable-anchor",
                            score=0.55,
                            visual_opacity_scale=0.7,
                            visual_width_scale=0.9,
                            line_ink=0.009,
                        ),
                    ],
                },
            )
            write_json(
                Path(config.model_path),
                {
                    "schema_version": 1,
                    "method": "test-model",
                    "candidate_scores": {
                        "failure-observed": {
                            "preference_score": 10.0,
                            "uncertainty": 0.1,
                            "both_bad_count": 2.0,
                            "failure_penalty": 2.0,
                        },
                        "stable-anchor": {
                            "preference_score": 1.0,
                            "uncertainty": 0.1,
                            "both_bad_count": 0.0,
                            "failure_penalty": 0.0,
                        },
                    },
                },
            )

            suggestions = suggest_configurations(config, limit=1)

            self.assertEqual(suggestions["input"]["stable_base_candidate_count"], 1)
            self.assertEqual(suggestions["input"]["failure_observed_candidate_count"], 1)
            self.assertEqual(suggestions["suggestions"][0]["nearest_observed_candidate"], "stable-anchor")
            self.assertTrue(suggestions["suggestions"][0]["base_model_signal"]["stable_anchor_base"])

    def test_suggest_interleaves_sources_before_reusing_source_anchor(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = make_fixture(Path(tmp))
            write_json(
                Path(config.manifest_path),
                {
                    "schema_version": 1,
                    "candidate_count": 3,
                    "candidates": [
                        make_optimizer_candidate(
                            "portrait-top",
                            score=0.99,
                            visual_opacity_scale=0.8,
                            visual_width_scale=0.9,
                            line_ink=0.009,
                            source_id="portrait",
                            line_count=5400,
                        ),
                        make_optimizer_candidate(
                            "portrait-second",
                            score=0.98,
                            visual_opacity_scale=0.8,
                            visual_width_scale=0.9,
                            line_ink=0.0091,
                            source_id="portrait",
                            line_count=5500,
                        ),
                        make_optimizer_candidate(
                            "pet-anchor",
                            score=0.4,
                            visual_opacity_scale=0.8,
                            visual_width_scale=0.9,
                            line_ink=0.0092,
                            source_id="pet",
                            line_count=5600,
                        ),
                    ],
                },
            )
            write_json(
                Path(config.model_path),
                {
                    "schema_version": 1,
                    "method": "test-model",
                    "candidate_scores": {
                        "portrait-top": {"preference_score": 10.0, "uncertainty": 0.1},
                        "portrait-second": {"preference_score": 9.0, "uncertainty": 0.1},
                        "pet-anchor": {"preference_score": 1.0, "uncertainty": 0.1},
                    },
                },
            )

            suggestions = suggest_configurations(config, limit=2)

            self.assertEqual(suggestions["input"]["eligible_source_count"], 2)
            self.assertEqual(
                [suggestion["source_id"] for suggestion in suggestions["suggestions"]],
                ["portrait", "pet"],
            )
            self.assertEqual(
                [suggestion["nearest_observed_candidate"] for suggestion in suggestions["suggestions"]],
                ["portrait-top", "pet-anchor"],
            )

    def test_review_queue_selection_interleaves_sources_before_reusing_source(self):
        rows = [
            make_queue_row("source-a-high", "source-a", 0.99),
            make_queue_row("source-a-next", "source-a", 0.98),
            make_queue_row("source-b-lower", "source-b", 0.4),
        ]

        selected = select_review_rows(rows, limit=2)

        self.assertEqual([row["source_id"] for row in selected], ["source-a", "source-b"])

    def test_source_suite_writes_manifest_and_dataset_template(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = build_source_suite(output_dir=tmp, download=False)
            dataset = json.loads((Path(tmp) / "dataset.json").read_text(encoding="utf-8"))

            self.assertEqual(report["source_count"], len(ROBUSTNESS_SOURCE_SPECS))
            self.assertEqual(report["downloaded_count"], 0)
            self.assertEqual(len(dataset["pairs"]), len(ROBUSTNESS_SOURCE_SPECS))
            self.assertIn("face", report["category_coverage"])
            self.assertIn("small_offcenter_subject", report["category_coverage"])
            for pair in dataset["pairs"]:
                self.assertEqual(pair["source"], pair["target"])
                self.assertTrue(pair["source"].startswith("images/"))
                self.assertIn("sourceCategory", pair)

    def test_validate_runner_robustness_dataset_accepts_square_source_target_pairs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "sources").mkdir()
            (root / "targets").mkdir()
            (root / "originals").mkdir()
            pairs = []
            for index in range(1, 10):
                source_name = f"source-{index:02d}.jpg"
                target_name = f"target-{index:02d}.jpg"
                write_fake_jpeg_header(root / "sources" / source_name, width=1000, height=1000)
                write_fake_jpeg_header(root / "targets" / target_name, width=1000, height=1000)
                write_fake_jpeg_header(root / "originals" / source_name, width=1280, height=900)
                pairs.append(
                    {
                        "id": f"pair-{index}",
                        "source": f"sources/{source_name}",
                        "target": f"targets/{target_name}",
                        "sourceDimensions": {"width": 1000, "height": 1000},
                        "targetDimensions": {"width": 1000, "height": 1000},
                        "sourceCategory": "fixture",
                    }
                )
            write_json(root / "dataset.json", {"name": "fixture", "pairs": pairs})
            write_json(root / "manifest.json", {"name": "fixture", "sourceCount": 9})

            report = validate_runner_robustness_dataset(dataset_dir=str(root))

            self.assertTrue(report["valid"])
            self.assertEqual(report["pair_count"], 9)
            self.assertEqual(report["source_target_jpeg_count"], 18)
            self.assertEqual(report["source_target_1000_square_count"], 18)
            self.assertEqual(report["missing_proxy_pairs"], [])

    def test_ingest_prefers_artifact_source_hash_over_default_dataset_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = make_fixture(Path(tmp))
            fallback_source = (
                Path(config.stringartio_root)
                / "experiments"
                / "rl-training"
                / "originals"
                / "fallback-source.png"
            )
            fallback_source.write_bytes(b"fallback-source")
            write_json(
                Path(config.stringartio_root) / "experiments" / "rl-training" / "dataset.json",
                {
                    "pairs": [
                        {
                            "id": "pair-1",
                            "source": "originals/fallback-source.png",
                            "target": "targets/target-1.png",
                        }
                    ]
                },
            )

            manifest = ingest_experiments(config)
            source_path = Path(config.stringartio_root) / "experiments" / "rl-training" / "originals" / "source-1.png"

            self.assertEqual(manifest["candidate_count"], 2)
            self.assertEqual(
                {candidate["source_hash"] for candidate in manifest["candidates"]},
                {sha256_file(source_path)},
            )

    def test_suggest_excludes_preference_lab_ids_with_regenerated_runtime_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = make_fixture(Path(tmp))
            write_json(
                Path(config.manifest_path),
                {
                    "schema_version": 1,
                    "candidate_count": 4,
                    "candidates": [
                        make_optimizer_candidate(
                            "stale-risk-episode::pair-1::r1-a",
                            score=0.99,
                            visual_opacity_scale=1,
                            visual_width_scale=1,
                            line_ink=0.009,
                            runtime_ms=29000,
                        ),
                        make_optimizer_candidate(
                            "stale-risk-episode::pair-2::r1-b",
                            score=0.98,
                            visual_opacity_scale=1,
                            visual_width_scale=1,
                            line_ink=0.009,
                            runtime_ms=29000,
                        ),
                        make_optimizer_candidate(
                            "regenerated-slow-same-suggestion::pair-1::r1-c",
                            score=0.95,
                            visual_opacity_scale=1,
                            visual_width_scale=1,
                            line_ink=0.009,
                            runtime_ms=71000,
                            metadata={
                                "preference_lab": {
                                    "suggestion_id": "suggestion-runtime-risk",
                                    "nearest_observed_candidate": "stale-risk-episode::pair-1::r1-a",
                                },
                            },
                        ),
                        make_optimizer_candidate(
                            "safe-visible-anchor",
                            score=0.4,
                            visual_opacity_scale=0.7,
                            visual_width_scale=0.9,
                            line_ink=0.009,
                            runtime_ms=22000,
                            metadata={
                                "preference_lab": {
                                    "suggestion_id": "suggestion-safe",
                                },
                            },
                        ),
                    ],
                },
            )
            write_json(
                Path(config.model_path),
                {
                    "schema_version": 1,
                    "method": "test-model",
                    "candidate_scores": {
                        "stale-risk-episode::pair-1::r1-a": {"preference_score": 10.0, "uncertainty": 0.1},
                        "stale-risk-episode::pair-2::r1-b": {"preference_score": 9.5, "uncertainty": 0.1},
                        "regenerated-slow-same-suggestion::pair-1::r1-c": {
                            "preference_score": 9.0,
                            "uncertainty": 0.1,
                        },
                        "safe-visible-anchor": {"preference_score": 1.0, "uncertainty": 0.1},
                    },
                },
            )

            suggestions = suggest_configurations(config, limit=2)

            self.assertEqual(suggestions["input"]["eligible_candidate_count"], 1)
            self.assertEqual(
                suggestions["input"]["constraint_rejection_counts"]["runtime_limit_ms"],
                1,
            )
            self.assertEqual(
                suggestions["input"]["constraint_rejection_counts"][
                    "preference_lab_regenerated_runtime_limit_ms"
                ],
                3,
            )
            self.assertTrue(suggestions["suggestions"])
            self.assertTrue(
                all(
                    suggestion["nearest_observed_candidate"] == "safe-visible-anchor"
                    for suggestion in suggestions["suggestions"]
                )
            )

    def test_preference_lab_metadata_is_not_model_feature(self):
        rows = [
            {
                "candidate_id": "candidate-a",
                "source_id": "pair-1",
                "preference_lab_expected_preference_score": "5.5",
                "derived_visible_ink_score": "0.003",
                "score": "0.4",
            }
        ]

        selected = select_feature_columns(rows)

        self.assertNotIn("preference_lab_expected_preference_score", selected)
        self.assertIn("derived_visible_ink_score", selected)

    def test_residual_diagnostics_are_exported_but_not_model_features(self):
        rows = [
            {
                "candidate_id": "candidate-a",
                "source_id": "pair-1",
                "metric_residual_luma_score": "0.12",
                "metric_rendered_residual_rgb_score": "0.22",
                "metric_visual_quality_score": "0.8",
            }
        ]

        selected = select_feature_columns(rows)

        self.assertNotIn("metric_residual_luma_score", selected)
        self.assertNotIn("metric_rendered_residual_rgb_score", selected)
        self.assertIn("metric_visual_quality_score", selected)

    def test_better_visibility_reason_flag_validates_and_maps_to_rendered_features(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = make_fixture(Path(tmp))
            manifest = ingest_experiments(config)
            candidates = load_candidate_manifest(config.manifest_path)
            write_jsonl(
                Path(config.preference_path),
                [
                    {
                        "preference_id": "pref-visibility-001",
                        "source_id": "pair-1",
                        "candidate_a": candidates[0].candidate_id,
                        "candidate_b": candidates[1].candidate_id,
                        "winner": "A",
                        "reason_flags": ["better_visibility"],
                    }
                ],
            )

            preference_report = validate_preferences(config)

            self.assertEqual(manifest["candidate_count"], 2)
            self.assertEqual(preference_report["warning_count"], 0)
            self.assertIn("better_visibility", REASON_FLAG_FEATURE_TARGETS)
            self.assertIn(
                "rendered_svg_stroke_opacity_mean",
                REASON_FLAG_FEATURE_TARGETS["better_visibility"],
            )


def make_fixture(root: Path) -> LabConfig:
    stringartio = root / "stringartio"
    lab = root / "lab"
    run_dir = stringartio / "experiments" / "local-runs" / "run-a"
    output_dir = run_dir / "outputs" / "gen-a" / "clean"
    source_dir = stringartio / "experiments" / "rl-training" / "originals"
    target_dir = stringartio / "experiments" / "rl-training" / "targets"
    output_dir.mkdir(parents=True)
    source_dir.mkdir(parents=True)
    target_dir.mkdir(parents=True)
    write_json(
        stringartio / "docs" / "string-art" / "generation-quality-contract.json",
        make_generation_quality_contract(),
    )
    (source_dir / "source-1.png").write_bytes(b"source")
    (target_dir / "target-1.png").write_bytes(b"target")
    (output_dir / "a.svg").write_text(
        """
        <svg xmlns="http://www.w3.org/2000/svg">
          <g stroke="#111" stroke-width="1.2" stroke-opacity="0.012">
            <line x1="0" y1="0" x2="10" y2="10" />
            <line x1="0" y1="10" x2="10" y2="0" />
          </g>
        </svg>
        """,
        encoding="utf-8",
    )
    (output_dir / "b.svg").write_text(
        """
        <svg xmlns="http://www.w3.org/2000/svg">
          <g stroke="#111" stroke-width="1.0" stroke-opacity="0.01">
            <line x1="1" y1="0" x2="9" y2="10" />
            <line x1="1" y1="10" x2="9" y2="0" />
          </g>
        </svg>
        """,
        encoding="utf-8",
    )
    (output_dir / "a-comparison.png").write_bytes(b"a")
    (output_dir / "b-comparison.png").write_bytes(b"b")

    write_json(
        stringartio / "experiments" / "rl-training" / "dataset.json",
        {
            "pairs": [
                {
                    "id": "pair-1",
                    "source": "originals/source-1.png",
                    "target": "targets/target-1.png",
                }
            ]
        },
    )
    write_json(run_dir / "manifest.json", {"runId": "run-a", "preset": "clean-app-ready"})
    write_json(
        run_dir / "artwork-quality-summary.json",
        {
            "runId": "run-a",
            "preset": "clean-app-ready",
            "candidates": [
                make_artwork_candidate("cand-a", "a", 0.7, 0.62),
                make_artwork_candidate("cand-b", "b", 0.62, 0.58),
            ],
        },
    )
    write_json(run_dir / "results.json", {"episodes": []})

    return LabConfig(
        stringartio_root=str(stringartio),
        experiments_path=str(stringartio / "experiments"),
        output_path=str(lab / "data" / "processed"),
        preference_path=str(lab / "data" / "preferences" / "preferences.jsonl"),
        feature_table_path=str(lab / "data" / "processed" / "features.csv"),
        review_queue_path=str(lab / "data" / "review_queue" / "review_queue.jsonl"),
        manifest_path=str(lab / "data" / "processed" / "candidate_manifest.json"),
        model_path=str(lab / "data" / "processed" / "preference_model.json"),
        suggestions_path=str(lab / "data" / "suggestions" / "suggested-configs.json"),
    )


def generation_quality_contract_path(config: LabConfig) -> Path:
    return Path(config.stringartio_root) / "docs" / "string-art" / "generation-quality-contract.json"


def add_fixture_artwork_run(config: LabConfig, run_id: str, stem: str, score: float, ssim: float):
    run_dir = Path(config.experiments_path) / "local-runs" / run_id
    output_dir = run_dir / "outputs" / "gen-a" / "clean"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / f"{stem}.svg").write_text("<svg></svg>", encoding="utf-8")
    (output_dir / f"{stem}-comparison.png").write_bytes(stem.encode("utf-8"))
    write_json(run_dir / "manifest.json", {"runId": run_id, "preset": "clean-app-ready"})
    write_json(
        run_dir / "artwork-quality-summary.json",
        {
            "runId": run_id,
            "preset": "clean-app-ready",
            "candidates": [
                make_artwork_candidate(
                    f"cand-{stem}",
                    stem,
                    score,
                    ssim,
                    run_id=run_id,
                )
            ],
        },
    )
    write_json(run_dir / "results.json", {"episodes": []})


def make_generation_quality_contract(
    runtime_target_ms=30000,
    line_count_limit=6000,
    preferred_line_min=5200,
    preferred_line_max=5800,
    min_line_ink=0.0085,
    target_line_ink=0.009,
    target_visible_ink=0.0055,
):
    return {
        "schemaVersion": 1,
        "contractId": "stringartio-generation-quality-contract",
        "version": "test-contract",
        "appReady": {
            "allowedQualityModeKeys": ["clean", "accurate"],
            "humanReviewRequired": True,
            "lineCountLimit": line_count_limit,
            "maxPinCount": 768,
            "preferredLineCountRange": {
                "min": preferred_line_min,
                "max": preferred_line_max,
            },
            "promotionProfileKey": "clean",
            "runtimeTargetMs": runtime_target_ms,
        },
        "forbiddenConfigFields": {
            "truthyOrNonzero": [
                "targetAwareLineReweighting",
                "targetGuidanceStrength",
                "targetAwarePruneRatio",
                "targetAwareSoftPruneRatio",
                "sourcePseudoTargetStrength",
            ],
        },
        "preferenceLabSuggestion": {
            "comparisonSize": 192,
            "repeatCount": 5,
            "runtimeTargetMs": runtime_target_ms,
            "sampleSize": 192,
        },
        "qualityModel": {
            "name": "perceptual-string-art-v2",
        },
        "visibility": {
            "minLineInk": min_line_ink,
            "minVisibleInk": 0.004,
            "minVisualOpacityScale": 0.6,
            "minVisualWidthScale": 0.8,
            "policy": "minimum_floor_plus_app_upload_target",
            "targetLineInk": target_line_ink,
            "targetVisibleInk": target_visible_ink,
            "targetVisualOpacityScale": 0.7,
            "targetVisualWidthScale": 0.9,
        },
    }


def make_artwork_candidate(candidate_id, stem, score, ssim, run_id="run-a"):
    return {
        "candidateId": candidate_id,
        "artworkPrimary": score,
        "eligible": True,
        "originLanes": ["app-ready-artwork"],
        "profileKey": "clean",
        "config": {
            "qualityModeKey": "clean",
            "pinCount": 600,
            "threadCount": 4800,
            "threadThickness": 7,
            "lineInk": 0.009,
            "visualOpacityScale": 0.7,
            "visualWidthScale": 0.9,
            "targetAwareLineReweighting": False,
            "targetGuidanceStrength": 0,
        },
        "metrics": {
            "ssim": ssim,
            "edgeSimilarity": 0.74,
            "mae": 0.2,
            "mse": 0.08,
            "detailScore": 0.7,
            "contrastScore": 0.55,
            "finalLineCount": 4800,
            "totalMs": 22000,
            "visualQualityScore": score,
            "targetScore": 0.6,
            "lineClumpPenalty": 0.02,
            "overdrawRate": 0.2,
        },
        "artifacts": [
            {
                "inputId": "pair-1",
                "sourcePath": "experiments/rl-training/originals/source-1.png",
                "targetPath": "experiments/rl-training/targets/target-1.png",
                "outputPath": f"experiments/local-runs/{run_id}/outputs/gen-a/clean/{stem}.svg",
                "comparisonPath": f"experiments/local-runs/{run_id}/outputs/gen-a/clean/{stem}-comparison.png",
                "score": score,
            }
        ],
    }


def make_queue_candidate(candidate_id, score, clump, overdraw, line_count, metadata=None):
    return {
        "run_id": "run-a",
        "candidate_id": candidate_id,
        "source_id": "pair-1",
        "source_hash": "source-hash",
        "config": {
            "qualityModeKey": "clean",
            "pinCount": 600,
            "threadCount": line_count,
            "finalLineCap": line_count,
            "lineInk": 0.0083,
            "visualOpacityScale": 0.5,
            "visualWidthScale": 0.75,
            "targetAwareLineReweighting": False,
            "targetGuidanceStrength": 0,
        },
        "metrics": {
            "ssim": score,
            "edgeSimilarity": score,
            "detailScore": score,
            "contrastScore": score,
            "finalLineCount": line_count,
            "totalMs": 22000,
            "visualQualityScore": score,
            "targetScore": score,
            "lineClumpPenalty": clump,
            "overdrawRate": overdraw,
        },
        "artifact_paths": {
            "output": f"/tmp/{candidate_id}.svg",
            "comparison": f"/tmp/{candidate_id}-comparison.png",
        },
        "runtime_ms": 22000,
        "line_count": line_count,
        "app_ready": True,
        "score": score,
        "metadata": metadata or {},
    }


def make_queue_row(queue_id, source_id, priority):
    return {
        "queue_id": queue_id,
        "source_id": source_id,
        "candidate_a": f"{queue_id}-a",
        "candidate_b": f"{queue_id}-b",
        "priority": priority,
        "selection_reasons": {
            "anchor_pair": 0.0,
            "double_failure_risk": 0.0,
        },
    }


def make_optimizer_candidate(
    candidate_id,
    score,
    visual_opacity_scale,
    visual_width_scale,
    line_ink,
    runtime_ms=22000,
    line_count=4800,
    metadata=None,
    source_id="pair-1",
):
    return {
        "run_id": "run-a",
        "candidate_id": candidate_id,
        "source_id": source_id,
        "source_hash": "source-hash",
        "config": {
            "qualityModeKey": "clean",
            "pinCount": 600,
            "threadCount": line_count,
            "finalLineCap": line_count,
            "lineInk": line_ink,
            "visualOpacityScale": visual_opacity_scale,
            "visualWidthScale": visual_width_scale,
            "targetAwareLineReweighting": False,
            "targetGuidanceStrength": 0,
        },
        "metrics": {
            "totalMs": runtime_ms,
            "finalLineCount": line_count,
            "visualQualityScore": score,
        },
        "artifact_paths": {},
        "runtime_ms": runtime_ms,
        "line_count": line_count,
        "app_ready": True,
        "score": score,
        "metadata": metadata or {},
    }


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def write_fake_jpeg_header(path: Path, width: int, height: int):
    path.write_bytes(
        b"\xff\xd8"
        + b"\xff\xc0"
        + b"\x00\x11"
        + b"\x08"
        + height.to_bytes(2, "big")
        + width.to_bytes(2, "big")
        + b"\x03\x01\x11\x00\x02\x11\x00\x03\x11\x00"
        + b"\xff\xd9"
    )


def write_jsonl(path: Path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
