import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from .config import LabConfig, create_example_config
from .demo import run_public_demo
from .evaluation import evaluate_preference_model
from .features import build_feature_table
from .ingest import ingest_experiments
from .model import train_preference_model
from .optimizer import suggest_configurations
from .preferences import validate_preferences
from .review_queue import generate_review_queue
from .review_app import ReviewStore, run_review_server
from .source_suite import build_source_suite, validate_runner_robustness_dataset
from .utils import project_root


def main(argv: Optional[list] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = dispatch(args)
    except KeyboardInterrupt:
        return 130
    emit_json(result)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="stringart-lab")
    parser.add_argument("--config", help="Path to lab config JSON. Defaults to ./lab-config.json or built-in defaults.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_config = subparsers.add_parser("init-config", help="Write a starter lab config.")
    init_config.add_argument("--path", default="lab-config.json")
    init_config.add_argument("--stringartio-root")
    init_config.add_argument("--dry-run", action="store_true")

    validate_config = subparsers.add_parser("validate-config", help="Validate configured paths.")
    validate_config.add_argument("--create-dirs", action="store_true")

    ingest = subparsers.add_parser("ingest", help="Read experiments and write candidate_manifest.json.")
    ingest.add_argument("--dry-run", action="store_true")
    ingest.add_argument("--limit-runs", type=int)
    ingest.add_argument("--run-id", help="Ingest only experiments/local-runs/<runId>.")

    features = subparsers.add_parser("features", help="Build numeric feature CSV from the manifest.")
    features.add_argument("--dry-run", action="store_true")

    validate_preferences_parser = subparsers.add_parser("validate-preferences", help="Validate preferences.jsonl.")
    validate_preferences_parser.set_defaults(validate_preferences=True)

    queue = subparsers.add_parser("queue", help="Generate blind same-source review pairs.")
    queue.add_argument("--limit", type=int, default=100)
    queue.add_argument("--max-pairs-per-source", type=int)
    queue.add_argument("--seed", type=int, default=20260626)
    queue.add_argument("--dry-run", action="store_true")

    train = subparsers.add_parser("train-model", help="Train the baseline pairwise preference model.")
    train.add_argument("--learning-rate", type=float, default=0.05)
    train.add_argument("--epochs", type=int, default=600)
    train.add_argument("--l2", type=float, default=0.001)
    train.add_argument("--dry-run", action="store_true")

    suggest = subparsers.add_parser(
        "suggest",
        help="Write constrained preference-guided search suggestions.",
    )
    suggest.add_argument("--limit", type=int, default=10)
    suggest.add_argument("--runtime-limit-ms", type=int, default=None)
    suggest.add_argument("--line-count-limit", type=int, default=None)
    suggest.add_argument("--min-visual-opacity-scale", type=float, default=None)
    suggest.add_argument("--min-visual-width-scale", type=float, default=None)
    suggest.add_argument("--min-line-ink", type=float, default=None)
    suggest.add_argument("--min-visible-ink", type=float, default=None)
    suggest.add_argument("--target-visual-opacity-scale", type=float, default=None)
    suggest.add_argument("--target-visual-width-scale", type=float, default=None)
    suggest.add_argument("--target-line-ink", type=float, default=None)
    suggest.add_argument("--target-visible-ink", type=float, default=None)
    suggest.add_argument("--preferred-line-count-min", type=int, default=None)
    suggest.add_argument("--preferred-line-count-max", type=int, default=None)
    suggest.add_argument("--seed", type=int, default=20260626)
    suggest.add_argument("--dry-run", action="store_true")

    source_suite = subparsers.add_parser("source-suite", help="Download/write the robustness source image suite.")
    source_suite.add_argument("--output-dir", default=None)
    source_suite.add_argument("--skip-download", action="store_true")
    source_suite.add_argument("--force", action="store_true")
    source_suite.add_argument("--dry-run", action="store_true")

    robustness_dataset = subparsers.add_parser(
        "validate-robustness-dataset",
        help="Validate the runner-ready StringArtio robustness dataset.",
    )
    robustness_dataset.add_argument("--dataset-dir", default=None)

    evaluate = subparsers.add_parser(
        "evaluate",
        help="Evaluate metric and preference models with source/run holdouts.",
    )
    evaluate.add_argument("--output", default=None)
    evaluate.add_argument("--min-run-test-pairs", type=int, default=3)
    evaluate.add_argument("--dry-run", action="store_true")

    public_evaluate = subparsers.add_parser(
        "public-evaluate",
        help="Reproduce the reduced evaluation from the tracked anonymized fixture.",
    )
    public_evaluate.add_argument("--output", default=None)

    demo = subparsers.add_parser(
        "demo",
        help="Run the complete reduced public-fixture pipeline without StringArtio private data.",
    )
    demo.add_argument("--output", default=None)

    review = subparsers.add_parser("review", help="Start the tracked blind-review web UI.")
    review.add_argument("--host", default="127.0.0.1")
    review.add_argument("--port", type=int, default=8765)
    review.add_argument("--queue-path", default=None)
    review.add_argument("--preference-path", default=None)
    review.add_argument("--artifact-root", action="append", default=[])
    review.add_argument("--reviewer", default="local-review-ui")
    review.add_argument("--title", default="StringArtio blind preference review")

    pipeline = subparsers.add_parser("pipeline", help="Run ingest, features, preference validation, queue, model, and suggestions.")
    pipeline.add_argument("--dry-run", action="store_true")
    pipeline.add_argument("--limit-runs", type=int)
    pipeline.add_argument("--queue-limit", type=int, default=100)
    pipeline.add_argument("--suggestion-limit", type=int, default=10)
    pipeline.add_argument("--runtime-limit-ms", type=int, default=None)
    pipeline.add_argument("--line-count-limit", type=int, default=None)
    pipeline.add_argument("--min-visual-opacity-scale", type=float, default=None)
    pipeline.add_argument("--min-visual-width-scale", type=float, default=None)
    pipeline.add_argument("--min-line-ink", type=float, default=None)
    pipeline.add_argument("--min-visible-ink", type=float, default=None)
    pipeline.add_argument("--target-visual-opacity-scale", type=float, default=None)
    pipeline.add_argument("--target-visual-width-scale", type=float, default=None)
    pipeline.add_argument("--target-line-ink", type=float, default=None)
    pipeline.add_argument("--target-visible-ink", type=float, default=None)
    pipeline.add_argument("--preferred-line-count-min", type=int, default=None)
    pipeline.add_argument("--preferred-line-count-max", type=int, default=None)
    return parser


def dispatch(args: argparse.Namespace) -> Dict[str, Any]:
    if args.command == "init-config":
        config = create_example_config(args.path, args.stringartio_root, dry_run=args.dry_run)
        return {"command": args.command, "path": args.path, "dry_run": args.dry_run, "config": config.to_dict()}

    config = LabConfig.load(args.config)
    if args.command == "validate-config":
        warnings = config.validate(create_dirs=args.create_dirs)
        return {
            "command": args.command,
            "config": config.to_dict(),
            "warning_count": len(warnings),
            "warnings": [warning.to_dict() for warning in warnings],
        }
    if args.command == "ingest":
        manifest = ingest_experiments(
            config,
            dry_run=args.dry_run,
            limit_runs=args.limit_runs,
            run_id=args.run_id,
        )
        result = {
            "command": args.command,
            "candidate_count": manifest.get("candidate_count"),
            "created_at": manifest.get("created_at"),
            "manifest_path": config.manifest_path,
            "schema_version": manifest.get("schema_version"),
            "source": manifest.get("source"),
            "warning_count": len(manifest.get("warnings", [])),
            "warnings": manifest.get("warnings", []),
        }
        if args.run_id is not None:
            candidates = manifest.get("candidates", [])
            result.update(
                {
                    "run_id": args.run_id,
                    "candidate_source_ids": sorted(
                        {
                            str(candidate.get("source_id"))
                            for candidate in candidates
                            if candidate.get("source_id")
                        }
                    ),
                    "app_ready_count": sum(
                        1 for candidate in candidates if candidate.get("app_ready")
                    ),
                }
            )
        return result
    if args.command == "features":
        return {"command": args.command, **build_feature_table(config, dry_run=args.dry_run)}
    if args.command == "validate-preferences":
        return {"command": args.command, **validate_preferences(config)}
    if args.command == "queue":
        return {
            "command": args.command,
            **generate_review_queue(
                config,
                limit=args.limit,
                seed=args.seed,
                dry_run=args.dry_run,
                max_pairs_per_source=args.max_pairs_per_source,
            ),
        }
    if args.command == "train-model":
        model = train_preference_model(
            config,
            learning_rate=args.learning_rate,
            epochs=args.epochs,
            l2=args.l2,
            dry_run=args.dry_run,
        )
        return {
            "command": args.command,
            "trained": model.get("trained"),
            "method": model.get("method"),
            "reason": model.get("reason"),
            "training_examples": model.get("training_examples"),
            "pairwise_training_examples": model.get("pairwise_training_examples"),
            "tie_training_examples": model.get("tie_training_examples"),
            "failure_training_examples": model.get("failure_training_examples"),
            "reason_flag_training_examples": model.get("reason_flag_training_examples"),
            "candidate_score_count": len(model.get("candidate_scores", {})),
            "model_path": config.model_path,
            "warning_count": len(model.get("warnings", [])),
            "warnings": model.get("warnings", []),
        }
    if args.command == "suggest":
        return {
            "command": args.command,
            **suggest_configurations(
                config,
                limit=args.limit,
                runtime_limit_ms=args.runtime_limit_ms,
                line_count_limit=args.line_count_limit,
                min_visual_opacity_scale=args.min_visual_opacity_scale,
                min_visual_width_scale=args.min_visual_width_scale,
                min_line_ink=args.min_line_ink,
                min_visible_ink=args.min_visible_ink,
                target_visual_opacity_scale=args.target_visual_opacity_scale,
                target_visual_width_scale=args.target_visual_width_scale,
                target_line_ink=args.target_line_ink,
                target_visible_ink=args.target_visible_ink,
                preferred_line_count_min=args.preferred_line_count_min,
                preferred_line_count_max=args.preferred_line_count_max,
                seed=args.seed,
                dry_run=args.dry_run,
            ),
        }
    if args.command == "source-suite":
        return {
            "command": args.command,
            **build_source_suite(
                output_dir=args.output_dir,
                download=not args.skip_download,
                force=args.force,
                dry_run=args.dry_run,
            ),
        }
    if args.command == "validate-robustness-dataset":
        return {
            "command": args.command,
            **validate_runner_robustness_dataset(
                dataset_dir=args.dataset_dir,
                stringartio_root=config.stringartio_root,
            ),
        }
    if args.command == "evaluate":
        output_path = args.output or str(Path(config.output_path) / "evaluation_report.json")
        return {
            "command": args.command,
            "output_path": output_path,
            **evaluate_preference_model(
                config,
                output_path=output_path,
                min_run_test_pairs=args.min_run_test_pairs,
                dry_run=args.dry_run,
            ),
        }
    if args.command == "public-evaluate":
        fixture_root = project_root() / "fixtures" / "public"
        public_config = LabConfig(
            stringartio_root=str(project_root()),
            experiments_path=str(fixture_root),
            output_path=str(fixture_root),
            preference_path=str(fixture_root / "preferences.jsonl"),
            feature_table_path=str(fixture_root / "features.csv"),
            review_queue_path=str(fixture_root / "unused-review-queue.jsonl"),
            manifest_path=str(fixture_root / "candidate_manifest.json"),
            model_path=str(fixture_root / "unused-model.json"),
            suggestions_path=str(fixture_root / "unused-suggestions.json"),
        )
        return {
            "command": args.command,
            "fixture": "fixtures/public",
            **evaluate_preference_model(
                public_config,
                output_path=args.output,
                min_run_test_pairs=1,
            ),
        }
    if args.command == "demo":
        return run_public_demo(output_dir=args.output)
    if args.command == "review":
        artifact_roots = [Path(path) for path in args.artifact_root]
        if not artifact_roots:
            artifact_roots = [Path(config.stringartio_root), Path.cwd()]
        store = ReviewStore(
            queue_path=Path(args.queue_path or config.review_queue_path),
            preference_path=Path(args.preference_path or config.preference_path),
            artifact_roots=artifact_roots,
            reviewer=args.reviewer,
            title=args.title,
        )
        run_review_server(store, host=args.host, port=args.port)
        return {"command": args.command, "stopped": True}
    if args.command == "pipeline":
        return run_pipeline(config, args)
    raise ValueError(f"Unknown command: {args.command}")


def run_pipeline(config: LabConfig, args: argparse.Namespace) -> Dict[str, Any]:
    manifest = ingest_experiments(config, dry_run=args.dry_run, limit_runs=args.limit_runs)
    features = build_feature_table(config, manifest=manifest, dry_run=args.dry_run)
    preference_report = validate_preferences(config)
    queue = generate_review_queue(config, limit=args.queue_limit, dry_run=args.dry_run)
    model = train_preference_model(config, dry_run=args.dry_run)
    suggestions = suggest_configurations(
        config,
        limit=args.suggestion_limit,
        runtime_limit_ms=args.runtime_limit_ms,
        line_count_limit=args.line_count_limit,
        min_visual_opacity_scale=args.min_visual_opacity_scale,
        min_visual_width_scale=args.min_visual_width_scale,
        min_line_ink=args.min_line_ink,
        min_visible_ink=args.min_visible_ink,
        target_visual_opacity_scale=args.target_visual_opacity_scale,
        target_visual_width_scale=args.target_visual_width_scale,
        target_line_ink=args.target_line_ink,
        target_visible_ink=args.target_visible_ink,
        preferred_line_count_min=args.preferred_line_count_min,
        preferred_line_count_max=args.preferred_line_count_max,
        dry_run=args.dry_run,
    )
    return {
        "command": "pipeline",
        "dry_run": args.dry_run,
        "steps": {
            "ingest": {
                "candidate_count": manifest.get("candidate_count"),
                "warning_count": len(manifest.get("warnings", [])),
            },
            "features": features,
            "preferences": preference_report,
            "queue": queue,
            "model": {
                "trained": model.get("trained"),
                "method": model.get("method"),
                "training_examples": model.get("training_examples"),
                "pairwise_training_examples": model.get("pairwise_training_examples"),
                "tie_training_examples": model.get("tie_training_examples"),
                "failure_training_examples": model.get("failure_training_examples"),
                "reason_flag_training_examples": model.get("reason_flag_training_examples"),
            },
            "suggestions": {
                "suggestion_count": len(suggestions.get("suggestions", [])),
                "eligible_candidate_count": suggestions.get("input", {}).get("eligible_candidate_count"),
            },
        },
    }


def emit_json(value: Dict[str, Any]) -> None:
    json.dump(value, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
