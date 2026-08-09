from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import LabConfig
from .ingest import load_candidate_manifest
from .schema import Candidate
from .utils import flatten_numeric, first_number, snake_case, write_csv


CANONICAL_METRIC_KEYS = [
    "ssim",
    "edgeSimilarity",
    "mae",
    "mse",
    "detailScore",
    "contrastScore",
    "darknessSimilarity",
    "runtimeMs",
    "totalMs",
    "finalLineCount",
    "visualQualityScore",
    "targetScore",
    "localizedDetailScore",
    "faceDetailScore",
    "lineClumpPenalty",
    "overdrawRate",
    "coverageRate",
    "positiveCoverageRate",
    "residualLumaScore",
    "residualRgbScore",
    "renderedResidualLumaScore",
    "renderedResidualRgbScore",
    "predictedDarkness",
    "renderedDarkness",
    "targetMapResidualDelta",
    "removedLineCount",
    "replacementCount",
    "pruningImprovement",
    "localSearchResidualDelta",
]

CANONICAL_CONFIG_KEYS = [
    "pinCount",
    "threadCount",
    "threadThickness",
    "lineInk",
    "finalLineCap",
    "cleanupLineInkScale",
    "cleanupStartRatio",
    "cleanupTargetBoost",
    "cleanupOverdrawPenaltyScale",
    "cleanupDensityPenaltyScale",
    "cleanupQuietPenaltyScale",
    "cleanupGlobalCandidateScale",
    "cleanupHotspotCount",
    "cleanupHotspotCandidateScale",
    "cleanupHotspotScoreBoost",
    "visualOpacityScale",
    "visualWidthScale",
    "visualTaperStartRatio",
    "visualTaperStrength",
    "contrast",
    "gamma",
    "foregroundFocusStrength",
    "backgroundSuppressionStrength",
]


def build_feature_table(
    config: LabConfig,
    manifest: Optional[Dict[str, Any]] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    if manifest is not None:
        candidates = [Candidate.from_dict(raw) for raw in manifest.get("candidates", [])]
    else:
        candidates = load_candidate_manifest(config.manifest_path)

    rows = [candidate_to_feature_row(candidate) for candidate in candidates]
    columns = write_csv(Path(config.feature_table_path), rows, dry_run=dry_run)
    return {
        "candidate_count": len(candidates),
        "row_count": len(rows),
        "column_count": len(columns),
        "columns": columns,
        "path": config.feature_table_path,
        "dry_run": dry_run,
    }


def candidate_to_feature_row(candidate: Candidate) -> Dict[str, Any]:
    row: Dict[str, Any] = {
        "candidate_id": candidate.candidate_id,
        "source_id": candidate.source_id,
        "source_hash": candidate.source_hash or "",
        "run_id": candidate.run_id,
        "preset": candidate.preset or "",
        "lane": candidate.lane or "",
        "profile": candidate.profile or "",
        "app_ready": 1 if candidate.app_ready else 0,
        "score": empty_if_none(candidate.score),
        "runtime_ms": empty_if_none(candidate.runtime_ms),
        "line_count": empty_if_none(candidate.line_count),
        "artifact_output": candidate.artifact_paths.get("output") or "",
        "artifact_comparison": candidate.artifact_paths.get("comparison") or "",
        "artifact_source": candidate.artifact_paths.get("source") or "",
        "artifact_target": candidate.artifact_paths.get("target") or "",
    }
    preference_lab = candidate.metadata.get("preference_lab") or {}
    row.update(
        {
            "preference_lab_suggestion_id": preference_lab.get("suggestion_id") or "",
            "preference_lab_phase_id": preference_lab.get("phase_id") or "",
            "preference_lab_source_run_id": preference_lab.get("source_run_id") or "",
            "preference_lab_nearest_observed_candidate": preference_lab.get("nearest_observed_candidate") or "",
            "preference_lab_expected_preference_score": empty_if_none(
                first_number(preference_lab.get("expected_preference_score"))
            ),
        }
    )
    row["derived_visible_ink_score"] = empty_if_none(visible_ink_score(candidate.config))

    for key in CANONICAL_METRIC_KEYS:
        column = f"metric_{snake_case(key)}"
        row[column] = empty_if_none(first_number(candidate.metrics.get(key)))
    for key in CANONICAL_CONFIG_KEYS:
        column = f"config_{snake_case(key)}"
        row[column] = empty_if_none(first_number(candidate.config.get(key)))

    row.update(flatten_numeric("metric", candidate.metrics))
    row.update(flatten_numeric("config", candidate.config))
    row.update(flatten_numeric("quality", candidate.metadata.get("quality") or {}))
    row.update(flatten_numeric("geometry", candidate.metadata.get("geometry") or {}))
    row.update(flatten_numeric("dimensions", candidate.metadata.get("dimensions") or {}))
    row.update(flatten_numeric("rendered_svg", candidate.metadata.get("rendered_svg") or {}))
    return row


def empty_if_none(value: Any) -> Any:
    return "" if value is None else value


def visible_ink_score(config: Dict[str, Any]) -> Optional[float]:
    line_ink = first_number(config.get("lineInk"))
    opacity = first_number(config.get("visualOpacityScale"))
    width = first_number(config.get("visualWidthScale"))
    if line_ink is None or opacity is None or width is None:
        return None
    return line_ink * opacity * width
