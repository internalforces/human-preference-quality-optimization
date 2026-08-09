import shutil
from pathlib import Path
from typing import Any, Dict, Optional

from .config import LabConfig
from .evaluation import evaluate_preference_model
from .model import train_preference_model
from .optimizer import suggest_configurations
from .review_queue import generate_review_queue
from .utils import project_root, write_json


DEMO_FILENAMES = (
    "candidate_manifest.json",
    "features.csv",
    "review_queue.jsonl",
    "preference_model.json",
    "suggested-configs.json",
    "evaluation-report.json",
)


def run_public_demo(output_dir: Optional[str] = None) -> Dict[str, Any]:
    root = project_root()
    fixture_root = root / "fixtures" / "public"
    output = Path(output_dir) if output_dir else root / "examples" / "demo-output"
    output.mkdir(parents=True, exist_ok=True)

    manifest_path = output / "candidate_manifest.json"
    features_path = output / "features.csv"
    shutil.copyfile(fixture_root / "candidate_manifest.json", manifest_path)
    shutil.copyfile(fixture_root / "features.csv", features_path)

    config = LabConfig(
        stringartio_root=str(fixture_root / "stringartio-contract"),
        experiments_path=str(fixture_root),
        output_path=str(output),
        preference_path=str(fixture_root / "preferences.jsonl"),
        feature_table_path=str(features_path),
        review_queue_path=str(output / "review_queue.jsonl"),
        manifest_path=str(manifest_path),
        model_path=str(output / "preference_model.json"),
        suggestions_path=str(output / "suggested-configs.json"),
    )

    queue = generate_review_queue(config, limit=12, seed=20260809)
    model = train_preference_model(config)
    suggestions = suggest_configurations(config, limit=5, seed=20260809)
    suggestions["scope"] = "public_fixture_demo"
    suggestions["input"]["model_path"] = "preference_model.json"
    write_json(Path(config.suggestions_path), suggestions)

    evaluation = evaluate_preference_model(config, min_run_test_pairs=1)
    evaluation["scope"] = "public_fixture_demo"
    evaluation["fixture"] = "fixtures/public"
    write_json(output / "evaluation-report.json", evaluation)

    relative_output = portable_output_path(output, root)
    return {
        "command": "demo",
        "scope": "public_fixture_demo",
        "fixture": "fixtures/public",
        "output": relative_output,
        "candidate_count": queue["candidate_count"],
        "review_queue_count": queue["written_count"],
        "model_trained": bool(model.get("trained")),
        "suggestion_count": len(suggestions.get("suggestions", [])),
        "files": [str(Path(relative_output) / filename) for filename in DEMO_FILENAMES],
        "warning_count": len(evaluation.get("warnings", [])),
        "note": "Fixture output only; suggestions have not been executed by StringArtio.",
    }


def portable_output_path(output: Path, root: Path) -> str:
    try:
        return output.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(output.resolve())
